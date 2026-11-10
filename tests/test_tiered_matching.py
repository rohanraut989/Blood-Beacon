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
