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


def donor(name, phone="919876543210"):
    return mock_db.insert_donor(
        name=name, blood_group="O+", city="Kathmandu", area="Center",
        phone=phone, gender="M", date_of_birth="1990-01-01", weight_kg=70,
    )


def request_for(units=1):
    req = mock_db.insert_request(
        patient_name="Test Receiver", blood_group="O+", component="whole_blood",
        units=units, hospital_name="Test Hospital", city="Kathmandu",
        needed_by="2027-01-01", contact_phone="919999999999", created_by="staff",
    )
    mock_db.verify_request(req["id"], "staff")
    mock_db.update_request_status(req["id"], "active")
    return req


def confirm(client, donor_record, message_id):
    return client.post(
        "/internal/whatsapp-reply",
        json={"phone": donor_record["phone"], "text": "1", "message_id": message_id},
        headers={"X-Bridge-Secret": os.environ["BRIDGE_SECRET"]},
    )


def test_confirmation_notifies_receiver_once_with_exact_details(client):
    donor_record = donor("TEST Donor", "919111111111")
    req = request_for(units=2)
    alert = mock_db.insert_alert(req["id"], donor_record["id"], 1, "whatsapp")
    mock_db.update_alert_stage(alert["id"], "awaiting_confirm")

    with patch("app.requests.post", return_value=MagicMock(status_code=200)) as send:
        response = confirm(client, donor_record, "receiver-confirm-1")
        confirm(client, donor_record, "receiver-confirm-duplicate")

    assert response.status_code == 200
    receiver_messages = [
        call.kwargs["json"]["message"] for call in send.call_args_list
        if call.kwargs["json"]["phone"] == req["contact_phone"]
    ]
    assert len(receiver_messages) == 1
    assert receiver_messages[0] == (
        "Good news! TEST Donor (O+) has accepted your request and confirmed to donate "
        "for Test Receiver at Test Hospital, Kathmandu. Donor's number: 919111111111. "
        "You can contact the donor directly now. Track your request: "
        f"http://localhost/request/{req['id']} — BloodBeacon"
    )
    assert mock_db.get_alerts_for_request(req["id"])[0]["receiver_notified"] is True


def test_receiver_failure_does_not_change_confirmation(client):
    donor_record = donor("TEST Failure Donor", "919222222222")
    req = request_for(units=2)
    alert = mock_db.insert_alert(req["id"], donor_record["id"], 1, "whatsapp")
    mock_db.update_alert_stage(alert["id"], "awaiting_confirm")

    with patch("app.requests.post") as send:
        send.side_effect = [MagicMock(status_code=200), MagicMock(status_code=503)]
        response = confirm(client, donor_record, "receiver-failure-1")

    assert response.status_code == 200
    assert mock_db.get_alerts_for_request(req["id"])[0]["reply"] == "confirmed"
    assert any(
        entry["action"] == "receiver_notify_failed"
        and entry["entity"] == "alert"
        for entry in mock_db.get_audit_log()
    )


def test_fulfillment_notification_is_once_per_request(client):
    first = donor("TEST First Donor", "919333333333")
    second = donor("TEST Second Donor", "919444444444")
    req = request_for(units=2)
    for donor_record, suffix in ((first, "a"), (second, "b")):
        alert = mock_db.insert_alert(req["id"], donor_record["id"], 1, "whatsapp")
        mock_db.update_alert_stage(alert["id"], "awaiting_confirm")

    with patch("app.requests.post", return_value=MagicMock(status_code=200)) as send:
        confirm(client, first, "fulfill-" + "a")
        confirm(client, second, "fulfill-" + "b")
        client.get(f"/request/{req['id']}/status.json")

    fulfillment_messages = [
        call.kwargs["json"]["message"] for call in send.call_args_list
        if "your BloodBeacon request is fulfilled." in call.kwargs["json"]["message"]
    ]
    assert fulfillment_messages == [
        "All 2 unit(s) for Test Receiver are now confirmed — your BloodBeacon request "
        "is fulfilled. Wishing a speedy recovery. 🙏"
    ]
    assert mock_db.get_request(req["id"])["fulfilled_notified"] is True


def test_simulator_records_confirmation_and_fulfillment_messages(client):
    donor_record = donor("TEST Simulator Donor", "919555555555")
    req = request_for()
    alert = mock_db.insert_alert(req["id"], donor_record["id"], 1, "simulator")
    mock_db.update_alert_stage(alert["id"], "awaiting_confirm")

    with patch("app.requests.post") as send:
        confirm(client, donor_record, "simulator-confirm")

    send.assert_not_called()
    logs = mock_db.get_audit_log()
    assert any(entry["action"] == "receiver_notified" for entry in logs)
    assert any(entry["action"] == "fulfilled_notified" for entry in logs)
    assert any("Good news! TEST Simulator Donor" in entry["detail"] for entry in logs)
    assert any("All 1 unit(s) for Test Receiver" in entry["detail"] for entry in logs)
