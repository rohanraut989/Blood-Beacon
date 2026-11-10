import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["BRIDGE_SECRET"] = "test-secret-12345"
import tests.mock_db as mock_db
sys.modules["db"] = mock_db

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    mock_db.reset()
    with app.test_client() as test_client:
        yield test_client


def make_donor(index):
    return mock_db.insert_donor(
        name=f"Donor {index}", blood_group="O+", city="Kathmandu",
        area="Center", phone=f"9198765432{index:02d}", gender="M",
        date_of_birth="1990-01-01", weight_kg=70,
    )


def make_request(units=1):
    req = mock_db.insert_request(
        patient_name="Patient", blood_group="O+", component="whole_blood",
        units=units, hospital_name="Hospital", city="Kathmandu",
        needed_by="2027-01-01", contact_phone="919999999999", created_by="test",
    )
    mock_db.verify_request(req["id"], "system")
    return req


def reply(client, donor, text, message_id):
    return client.post(
        "/internal/whatsapp-reply",
        json={"phone": donor["phone"], "text": text, "message_id": message_id},
        headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]},
    )


def test_silent_donor_passes_and_next_slot_is_filled(client):
    donors = [make_donor(index) for index in range(3)]
    req = make_request()
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp", follow_redirects=True)
        first = mock_db.get_alerts_for_request(req["id"])[0]
        mock_db._test_alerts[first["id"]]["sent_at"] = (
            datetime.now() - timedelta(minutes=3)
        ).isoformat()
        client.get(f"/request/{req['id']}/status.json")

    alerts = mock_db.get_alerts_for_request(req["id"])
    assert alerts[0]["reply"] == "passed"
    assert alerts[1]["donor_id"] == donors[1]["id"]
    assert sum(alert["reply"] is None and alert["stage"] != "done" for alert in alerts) == 1
    assert any(entry["action"] == "cascade_passed" for entry in mock_db.get_audit_log())


def test_two_units_keep_exactly_two_active_asks(client):
    donors = [make_donor(index) for index in range(3)]
    req = make_request(units=2)
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
    alerts = mock_db.get_alerts_for_request(req["id"])
    assert len(alerts) == 2
    assert all(alert["reply"] is None for alert in alerts)


def test_late_passed_reply_resumes_and_fulfilment_stands_down_other_donor(client):
    donors = [make_donor(index) for index in range(3)]
    req = make_request(units=1)
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
        first = mock_db.get_alerts_for_request(req["id"])[0]
        mock_db.update_alert_reply(first["id"], "passed", stage="done")
        client.get(f"/request/{req['id']}/status.json")
        assert len(mock_db.get_alerts_for_request(req["id"])) == 2
        reply(client, donors[0], "2", "resume-1")
        reply(client, donors[0], "1", "resume-2")

    assert mock_db.get_request(req["id"])["status"] == "fulfilled"
    assert any(
        entry["action"] == "donor_resumed" for entry in mock_db.get_audit_log()
    )


def test_window_rule_changes_expiry_behavior(client):
    donor = make_donor(1)
    req = make_request()
    mock_db.insert_rule("CASCADE_WINDOW_MINUTES", "10")
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
        alert = mock_db.get_alerts_for_request(req["id"])[0]
        mock_db._test_alerts[alert["id"]]["sent_at"] = (
            datetime.now() - timedelta(minutes=3)
        ).isoformat()
        client.get(f"/request/{req['id']}/status.json")
    assert mock_db.get_alerts_for_request(req["id"])[0]["reply"] is None


def test_late_reply_after_fulfilment_gets_one_completed_close(client):
    donor = make_donor(1)
    req = make_request()
    with patch("app.requests.post", return_value=MagicMock(status_code=200)) as send:
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
        alert = mock_db.get_alerts_for_request(req["id"])[0]
        mock_db.update_alert_reply(alert["id"], "passed", stage="done")
        mock_db.update_request_status(req["id"], "fulfilled")
        reply(client, donor, "1", "late-1")
        reply(client, donor, "1", "late-2")
    closes = [
        call.kwargs["json"]["message"] for call in send.call_args_list
        if "already been completed" in call.kwargs["json"]["message"]
    ]
    assert len(closes) == 1


def test_fresh_exact_match_donor_with_no_history_is_asked(client):
    donor = mock_db.insert_donor(
        name="Fresh Exact", blood_group="A+", city="Kathmandu",
        area="Center", phone="919876543299", gender="M",
        date_of_birth="1990-01-01", weight_kg=70,
    )
    req = mock_db.insert_request(
        patient_name="A Patient", blood_group="A+", component="whole_blood",
        units=1, hospital_name="Hospital", city="Kathmandu",
        needed_by="2027-01-01", contact_phone="919999999999", created_by="test",
    )
    mock_db.verify_request(req["id"], "system")
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
    alerts = mock_db.get_alerts_for_request(req["id"])
    assert len(alerts) == 1
    assert alerts[0]["donor_id"] == donor["id"]


def test_fresh_exact_donor_survives_predictor_failure(client):
    donor = mock_db.insert_donor(
        name="Fresh Predictor Fallback", blood_group="A+", city="Kathmandu",
        area="Center", phone="919876543298", gender="M",
        date_of_birth="1990-01-01", weight_kg=70,
    )
    req = mock_db.insert_request(
        patient_name="A Patient", blood_group="A+", component="whole_blood",
        units=1, hospital_name="Hospital", city="Kathmandu",
        needed_by="2027-01-01", contact_phone="919999999998", created_by="test",
    )
    mock_db.verify_request(req["id"], "system")
    with patch("app.predictor.score_donor", side_effect=ValueError("model unavailable")):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=simulator")
    alerts = mock_db.get_alerts_for_request(req["id"])
    assert len(alerts) == 1
    assert alerts[0]["donor_id"] == donor["id"]


def test_fresh_exact_donor_survives_corrupt_predictor_model(client):
    donor = mock_db.insert_donor(
        name="Fresh Corrupt Model", blood_group="A+", city="Kathmandu",
        area="Center", phone="919876543297", gender="M",
        date_of_birth="1990-01-01", weight_kg=70,
    )
    req = mock_db.insert_request(
        patient_name="A Patient", blood_group="A+", component="whole_blood",
        units=1, hospital_name="Hospital", city="Kathmandu",
        needed_by="2027-01-01", contact_phone="919999999996", created_by="test",
    )
    mock_db.verify_request(req["id"], "system")
    with patch("app.predictor.score_donor", side_effect=EOFError("truncated model")):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=simulator")
    alerts = mock_db.get_alerts_for_request(req["id"])
    assert len(alerts) == 1
    assert alerts[0]["donor_id"] == donor["id"]


def test_registration_refills_existing_zero_match_request(client):
    req = mock_db.insert_request(
        patient_name="A Patient", blood_group="A+", component="whole_blood",
        units=1, hospital_name="Hospital", city="Kathmandu",
        needed_by="2027-01-01", contact_phone="919999999997", created_by="test",
    )
    mock_db.verify_request(req["id"], "system")
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
        assert mock_db.get_alerts_for_request(req["id"]) == []
        client.post("/register", data={
            "name": "New A Donor", "blood_group": "A+", "city": "Kathmandu",
            "area": "Center", "country": "91", "phone": "9876543296",
            "gender": "M", "date_of_birth": "1990-01-01", "weight_kg": "70",
        })
    alerts = mock_db.get_alerts_for_request(req["id"])
    assert len(alerts) == 1
    assert alerts[0]["cross_group"] is False
