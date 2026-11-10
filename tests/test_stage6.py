"""
Tests for Stage 6: WhatsApp Bridge Integration.

Tests for /health endpoint, /internal/whatsapp-reply processing,
reply message deduplication, and bridge contract validation.
"""

import pytest
import sys
import os
from datetime import date
from unittest.mock import patch, MagicMock

# Mock db before importing app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import mock_db
sys.modules['db'] = mock_db

import app as app_module
import eligibility
from app import app

# Test fixtures
@pytest.fixture
def client():
    """Create test client with mock db."""
    app.config['TESTING'] = True
    os.environ['BRIDGE_SECRET'] = 'test-secret-12345'
    with app.test_client() as client:
        mock_db.reset()
        yield client

class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_returns_200(self, client):
        """GET /health should return 200 with {ok: true}."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.get_json() == {"ok": True}

class TestWhatsAppReplyEndpoint:
    """Tests for /internal/whatsapp-reply endpoint."""
    
    def test_reply_returns_401_without_secret(self, client):
        """POST without X-Bridge-Secret header should return 401."""
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-123456", "text": "1", "message_id": "msg_1"}
        )
        assert response.status_code == 401
    
    def test_reply_returns_401_with_wrong_secret(self, client):
        """POST with wrong X-Bridge-Secret should return 401."""
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-123456", "text": "1", "message_id": "msg_1"},
            headers={"X-Bridge-Secret": "wrong-secret"}
        )
        assert response.status_code == 401
    
    def test_reply_unknown_phone_returns_200(self, client):
        """POST with unknown phone number should return 200 (idempotent)."""
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-9-999999", "text": "1", "message_id": "msg_1"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("status") == "no_donor_for_phone"
    
    @patch("app.requests.post")
    def test_reply_confirmed_updates_alert(self, mock_post, client):
        """Reply 2 then 1 advances recency and confirms the donor."""
        mock_post.return_value = MagicMock(status_code=200)
        # Create donor
        donor = mock_db.insert_donor(
            name="Test Donor",
            blood_group="O+",
            city="Kathmandu",
            area="Thamel",
            phone="+977-1-123456",
            gender="M",
            date_of_birth="1990-01-01",
            weight_kg=70
        )
        
        # Create request
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="O+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-555555",
            created_by="staff"
        )
        mock_db.verify_request(req["id"], "staff_alice")
        mock_db.update_request_status(req["id"], "active")
        
        # Create alert
        alert = mock_db.insert_alert(
            request_id=req["id"],
            donor_id=donor["id"],
            wave_no=1,
            channel="whatsapp"
        )
        
        # Send recency reply "2", then confirmation reply "1".
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-123456", "text": "2", "message_id": "msg_1a"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        assert response.get_json()["status"] == "awaiting_confirm"
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-123456", "text": "1", "message_id": "msg_1b"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("status") == "reply_recorded"
        assert data.get("reply") == "confirmed"
        assert any(
            "Can you come to Test Hospital to donate?" in call.kwargs["json"]["message"]
            for call in mock_post.call_args_list
        )
    
    @patch("app.requests.post")
    def test_reply_donated_recently_inserts_donation(self, mock_post, client):
        """Reply 1 to the recency question inserts a self-report donation."""
        mock_post.return_value = MagicMock(status_code=200)
        # Create donor
        donor = mock_db.insert_donor(
            name="Test Donor",
            blood_group="A+",
            city="Kathmandu",
            area="Thamel",
            phone="+977-1-234567",
            gender="F",
            date_of_birth="1995-05-15",
            weight_kg=65
        )
        
        # Create request and alert
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="A+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-555555",
            created_by="staff"
        )
        mock_db.verify_request(req["id"], "staff_alice")
        mock_db.update_request_status(req["id"], "active")
        
        alert = mock_db.insert_alert(
            request_id=req["id"],
            donor_id=donor["id"],
            wave_no=1,
            channel="whatsapp"
        )
        
        # Send reply "1"
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-234567", "text": "1", "message_id": "msg_2"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("reply") == "donated_recently"
        
        # Check that donation was inserted
        donations = mock_db.get_donations_for_donor(donor["id"])
        assert len(donations) > 0
        assert donations[0]["source"] == "self_report"
        assert any(
            "Thank you for letting us know" in call.kwargs["json"]["message"]
            for call in mock_post.call_args_list
        )
    
    def test_reply_declined_updates_alert(self, client):
        """Reply 2 then 2 marks the alert as declined."""
        donor = mock_db.insert_donor(
            name="Test Donor",
            blood_group="B+",
            city="Kathmandu",
            area="Thamel",
            phone="+977-1-345678",
            gender="M",
            date_of_birth="1992-08-20",
            weight_kg=75
        )
        
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="B+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-555555",
            created_by="staff"
        )
        mock_db.verify_request(req["id"], "staff_alice")
        mock_db.update_request_status(req["id"], "active")
        
        alert = mock_db.insert_alert(
            request_id=req["id"],
            donor_id=donor["id"],
            wave_no=1,
            channel="whatsapp"
        )
        
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-345678", "text": "2", "message_id": "msg_3a"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        assert response.get_json()["status"] == "awaiting_confirm"
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-345678", "text": "2", "message_id": "msg_3b"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("reply") == "declined"
    
    def test_reply_message_id_dedupe(self, client):
        """Posting same message_id twice should process only once."""
        donor = mock_db.insert_donor(
            name="Test Donor",
            blood_group="AB+",
            city="Kathmandu",
            area="Thamel",
            phone="+977-1-456789",
            gender="M",
            date_of_birth="1988-12-25",
            weight_kg=80
        )
        
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="AB+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-555555",
            created_by="staff"
        )
        mock_db.verify_request(req["id"], "staff_alice")
        mock_db.update_request_status(req["id"], "active")
        
        alert = mock_db.insert_alert(
            request_id=req["id"],
            donor_id=donor["id"],
            wave_no=1,
            channel="whatsapp"
        )
        
        # First reply
        response1 = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-456789", "text": "1", "message_id": "msg_dup_123"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        assert response1.status_code == 200
        assert response1.get_json().get("status") == "reply_recorded"
        
        # Second reply with same message_id (should be deduped)
        response2 = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-456789", "text": "1", "message_id": "msg_dup_123"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        assert response2.status_code == 200
        assert response2.get_json().get("status") == "already_processed"

    def test_recency_yes_defers_donor_and_closes_conversation(self, client):
        """Recency reply 1 records today's donation and makes the donor ineligible."""
        donor = mock_db.insert_donor(
            name="Recent Donor", blood_group="O+", city="Kathmandu",
            area="Thamel", phone="+977-1-777001", gender="M",
            date_of_birth="1990-01-01", weight_kg=70
        )
        req = mock_db.insert_request(
            patient_name="Patient", blood_group="O+", component="whole_blood",
            units=1, hospital_name="Test Hospital", city="Kathmandu",
            needed_by="2024-11-20", contact_phone="+977-1-555555",
            created_by="staff"
        )
        alert = mock_db.insert_alert(req["id"], donor["id"], 1, "whatsapp")

        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": donor["phone"], "text": "1", "message_id": "msg_recent"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )

        assert response.get_json()["reply"] == "donated_recently"
        saved_alert = mock_db.get_alerts_for_request(req["id"])[0]
        assert saved_alert["stage"] == "done"
        donations = mock_db.get_donations_for_donor(donor["id"])
        assert donations[0]["source"] == "self_report"
        assessment = eligibility.assess_donor(
            donor, donations,
            {"donation_gap_men_days": 90, "age_min": 18, "age_max": 65, "weight_min_kg": 45},
            date.today()
        )
        assert assessment["status"] == "deferred"

    def test_unclear_text_reasks_same_step_without_advancing(self, client):
        """Unclear replies re-ask and leave the current conversation stage unchanged."""
        donor = mock_db.insert_donor(
            name="Unclear Donor", blood_group="B+", city="Kathmandu",
            area="Thamel", phone="+977-1-777002", gender="M",
            date_of_birth="1990-01-01", weight_kg=70
        )
        req = mock_db.insert_request(
            patient_name="Patient", blood_group="B+", component="whole_blood",
            units=1, hospital_name="Test Hospital", city="Kathmandu",
            needed_by="2024-11-20", contact_phone="+977-1-555555",
            created_by="staff"
        )
        mock_db.insert_alert(req["id"], donor["id"], 1, "whatsapp")

        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": donor["phone"], "text": "maybe", "message_id": "msg_unclear_1"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        assert response.get_json()["stage"] == "awaiting_recency"
        assert mock_db.get_alerts_for_request(req["id"])[0]["stage"] == "awaiting_recency"

        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": donor["phone"], "text": "2", "message_id": "msg_unclear_2"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        assert response.get_json()["status"] == "awaiting_confirm"
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": donor["phone"], "text": "maybe", "message_id": "msg_unclear_3"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        assert response.get_json()["stage"] == "awaiting_confirm"
        assert mock_db.get_alerts_for_request(req["id"])[0]["stage"] == "awaiting_confirm"
    
    def test_reply_invalid_text_no_reask(self, client):
        """Invalid reply should return success but no action (reask handled by bridge)."""
        donor = mock_db.insert_donor(
            name="Test Donor",
            blood_group="O-",
            city="Kathmandu",
            area="Thamel",
            phone="+977-1-567890",
            gender="F",
            date_of_birth="1998-03-10",
            weight_kg=60
        )
        
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="O-",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-555555",
            created_by="staff"
        )
        mock_db.verify_request(req["id"], "staff_alice")
        mock_db.update_request_status(req["id"], "active")
        
        alert = mock_db.insert_alert(
            request_id=req["id"],
            donor_id=donor["id"],
            wave_no=1,
            channel="whatsapp"
        )
        
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-567890", "text": "xyz", "message_id": "msg_invalid"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert "invalid_reply" in data.get("status", "")
    
    def test_reply_request_fulfilled(self, client):
        """When enough confirmations, request should move to fulfilled."""
        # Create donor
        donor = mock_db.insert_donor(
            name="Test Donor",
            blood_group="A-",
            city="Kathmandu",
            area="Thamel",
            phone="+977-1-678901",
            gender="M",
            date_of_birth="1991-07-22",
            weight_kg=72
        )
        
        # Create request for 1 unit
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="A-",
            component="whole_blood",
            units=1,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-555555",
            created_by="staff"
        )
        mock_db.verify_request(req["id"], "staff_alice")
        mock_db.update_request_status(req["id"], "active")
        
        # Create alert
        alert = mock_db.insert_alert(
            request_id=req["id"],
            donor_id=donor["id"],
            wave_no=1,
            channel="whatsapp"
        )
        
        # Reply 2 to recency, then 1 to confirmation.
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-678901", "text": "2", "message_id": "msg_fulfill_a"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        assert response.get_json()["status"] == "awaiting_confirm"
        response = client.post(
            "/internal/whatsapp-reply",
            json={"phone": "+977-1-678901", "text": "1", "message_id": "msg_fulfill_b"},
            headers={"X-Bridge-Secret": "test-secret-12345"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("status") == "request_fulfilled"

class TestHealthAndBridgeStatus:
    """Tests for deployment health check."""
    
    def test_health_endpoint_running(self, client):
        """Verify /health is reachable and returns ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.get_json()["ok"] is True
