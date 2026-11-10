import os
import sys
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


def donor(name, group, city, phone):
    return mock_db.insert_donor(
        name=name, blood_group=group, city=city, area="Center",
        phone=phone, gender="M", date_of_birth="1990-01-01", weight_kg=70,
    )


def request_for(group="AB+", city="Kathmandu"):
    req = mock_db.insert_request(
        patient_name="Maya Rai", blood_group=group, component="whole_blood",
        units=1, hospital_name="City Hospital", city=city,
        needed_by="2026-12-01", contact_phone="9999999999", created_by="public",
    )
    mock_db.verify_request(req["id"], "system (auto)")
    return req


def test_exact_donors_precede_compatible_and_cross_group_message(client):
    exact = donor("Exact", "AB+", "Kathmandu", "919876543210")
    compatible = donor("Compatible", "A+", "Kathmandu", "919876543211")
    far = donor("Far", "A+", "Pokhara", "919876543212")
    req = request_for()

    with patch("app.requests.post", return_value=MagicMock(status_code=200)) as send:
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")

    alerts = mock_db.get_alerts_for_request(req["id"])
    assert [alert["donor_id"] for alert in alerts] == [exact["id"], compatible["id"], far["id"]]
    assert [alert["match_tier"] for alert in alerts] == [1, 2, 3]
    assert alerts[1]["cross_group"] is True
    assert "No AB+ donor was found nearby" in send.call_args_list[1].kwargs["json"]["message"]


def test_zero_match_page_is_honest_and_sends_nothing(client):
    req = request_for()
    with patch("app.requests.post") as send:
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
    response = client.get(f"/request/{req['id']}")
    assert b"No matching donors found near Kathmandu right now." in response.data
    assert b"donors are being alerted" not in response.data
    send.assert_not_called()


def test_far_compatible_donor_is_used_when_local_tiers_are_empty(client):
    far = donor("Far", "A+", "Pokhara", "919876543212")
    req = request_for()
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
    alerts = mock_db.get_alerts_for_request(req["id"])
    assert len(alerts) == 1
    assert alerts[0]["donor_id"] == far["id"]
    assert alerts[0]["match_tier"] == 3


def test_cross_group_two_step_flow_completes(client):
    compatible = donor("Compatible", "A+", "Kathmandu", "919876543211")
    req = request_for()
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
        first = client.post(
            "/internal/whatsapp-reply",
            json={"phone": compatible["phone"], "text": "2", "message_id": "tier-1"},
            headers={"X-Bridge-Secret": os.getenv("BRIDGE_SECRET", "")},
        )
        second = client.post(
            "/internal/whatsapp-reply",
            json={"phone": compatible["phone"], "text": "1", "message_id": "tier-2"},
            headers={"X-Bridge-Secret": os.getenv("BRIDGE_SECRET", "")},
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert mock_db.get_alerts_for_request(req["id"])[0]["reply"] == "confirmed"


def test_status_json_contract_empty_then_confirmed_donor(client):
    confirmed = donor("Confirmed Donor", "A+", "Kathmandu", "919876543211")
    req = request_for()
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
    empty = client.get(f"/request/{req['id']}/status.json")
    assert empty.status_code == 200
    assert empty.get_json()["confirmed"] == []
    assert empty.get_json()["confirmed_count"] == 0

    alert = mock_db.get_alerts_for_request(req["id"])[0]
    mock_db.update_alert_reply(alert["id"], "confirmed", stage="done")
    confirmed_response = client.get(f"/request/{req['id']}/status.json")
    payload = confirmed_response.get_json()
    assert payload["confirmed_count"] == 1
    assert payload["units_needed"] == 1
    assert payload["confirmed"] == [{
        "donor_name": confirmed["name"],
        "blood_group": confirmed["blood_group"],
        "donor_phone": confirmed["phone"],
    }]


def test_status_page_contains_live_confirmation_poller_and_popup(client):
    req = request_for()
    response = client.get(f"/request/{req['id']}")
    html = response.data.decode()
    assert "/status.json" in html
    assert "setInterval(pollStatus, 5000)" in html
    assert "A donor has confirmed!" in html
    assert "confirmation-popup-dismiss" in html


def _activate_with_donors(client, donors, units=1):
    req = mock_db.insert_request(
        patient_name="Backfill Patient", blood_group="AB+", component="whole_blood",
        units=units, hospital_name="City Hospital", city="Kathmandu",
        needed_by="2026-12-01", contact_phone="9999999999", created_by="public",
    )
    mock_db.verify_request(req["id"], "system (auto)")
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post(f"/request/{req['id']}/activate?staff=1&channel=whatsapp")
    return req


def test_decline_immediately_backfills_next_ranked_donor(client):
    donors = [donor(f"Donor {index}", "A+", "Kathmandu", f"91987654{3200 + index}") for index in range(11)]
    req = _activate_with_donors(client, donors)
    initial = mock_db.get_alerts_for_request(req["id"])
    assert len(initial) == 10
    first = initial[0]
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post("/internal/whatsapp-reply", json={
            "phone": donors[first["donor_id"] - 1]["phone"], "text": "2", "message_id": "decline-step-1",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
        client.post("/internal/whatsapp-reply", json={
            "phone": donors[first["donor_id"] - 1]["phone"], "text": "2", "message_id": "decline-step-2",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
    alerts = mock_db.get_alerts_for_request(req["id"])
    assert len(alerts) == 11
    assert alerts[-1]["donor_id"] == donors[-1]["id"]
    assert alerts[-1]["wave_no"] == first["wave_no"]


def test_donated_recently_immediately_backfills(client):
    donors = [donor(f"Donor {index}", "A+", "Kathmandu", f"91987654{3300 + index}") for index in range(11)]
    req = _activate_with_donors(client, donors)
    first = mock_db.get_alerts_for_request(req["id"])[0]
    phone = next(item["phone"] for item in donors if item["id"] == first["donor_id"])
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        response = client.post("/internal/whatsapp-reply", json={
            "phone": phone, "text": "1", "message_id": "recent-step-1",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
    assert response.status_code == 200
    assert len(mock_db.get_alerts_for_request(req["id"])) == 11


def test_no_backfill_when_units_are_already_met(client):
    donors = [donor(f"Donor {index}", "A+", "Kathmandu", f"91987654{3400 + index}") for index in range(11)]
    req = _activate_with_donors(client, donors)
    alerts = mock_db.get_alerts_for_request(req["id"])
    first = alerts[0]
    mock_db.update_alert_reply(first["id"], "confirmed", stage="done")
    second = alerts[1]
    donor_record = next(item for item in donors if item["id"] == second["donor_id"])
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        response = client.post("/internal/whatsapp-reply", json={
            "phone": donor_record["phone"], "text": "2", "message_id": "met-step-1",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
    assert response.status_code == 200
    assert len(mock_db.get_alerts_for_request(req["id"])) == 10


def test_cross_group_backfill_uses_disclosure_message(client):
    donors = [donor(f"Exact {index}", "AB+", "Kathmandu", f"91987654{3500 + index}") for index in range(10)]
    donors.append(donor("Cross Group", "A+", "Kathmandu", "919876543599"))
    req = _activate_with_donors(client, donors)
    first = mock_db.get_alerts_for_request(req["id"])[0]
    phone = next(item["phone"] for item in donors if item["id"] == first["donor_id"])
    with patch("app.requests.post", return_value=MagicMock(status_code=200)) as send:
        client.post("/internal/whatsapp-reply", json={
            "phone": phone, "text": "2", "message_id": "cross-step-1",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
        client.post("/internal/whatsapp-reply", json={
            "phone": phone, "text": "2", "message_id": "cross-step-2",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
    assert mock_db.get_alerts_for_request(req["id"])[-1]["cross_group"] is True
    assert "No AB+ donor was found nearby" in send.call_args_list[-1].kwargs["json"]["message"]


def test_backfill_skips_candidate_that_reaches_monthly_cap(client):
    donors = [donor(f"Donor {index}", "A+", "Kathmandu", f"91987654{3600 + index}") for index in range(12)]
    req = _activate_with_donors(client, donors)
    capped = donors[-2]
    for _ in range(4):
        capped_alert = mock_db.insert_alert(999, capped["id"], 1, "whatsapp")
        mock_db._test_alerts[capped_alert["id"]]["created_at"] = "2026-11-10T00:00:00+00:00"
    first = mock_db.get_alerts_for_request(req["id"])[0]
    first_phone = next(item["phone"] for item in donors if item["id"] == first["donor_id"])
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post("/internal/whatsapp-reply", json={
            "phone": first_phone, "text": "2", "message_id": "cap-step-1",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
        client.post("/internal/whatsapp-reply", json={
            "phone": first_phone, "text": "2", "message_id": "cap-step-2",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
    alerts = mock_db.get_alerts_for_request(req["id"])
    assert alerts[-1]["donor_id"] == donors[-1]["id"]
    assert capped["id"] not in [alert["donor_id"] for alert in alerts if alert["request_id"] == req["id"]]


def test_pool_exhaustion_does_not_change_request(client):
    donors = [donor(f"Donor {index}", "A+", "Kathmandu", f"91987654{3700 + index}") for index in range(10)]
    req = _activate_with_donors(client, donors)
    first = mock_db.get_alerts_for_request(req["id"])[0]
    phone = next(item["phone"] for item in donors if item["id"] == first["donor_id"])
    with patch("app.requests.post", return_value=MagicMock(status_code=200)):
        client.post("/internal/whatsapp-reply", json={
            "phone": phone, "text": "2", "message_id": "exhaust-step-1",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
        client.post("/internal/whatsapp-reply", json={
            "phone": phone, "text": "2", "message_id": "exhaust-step-2",
        }, headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]})
    assert len(mock_db.get_alerts_for_request(req["id"])) == 10
    assert mock_db.get_request(req["id"])["status"] == "active"
