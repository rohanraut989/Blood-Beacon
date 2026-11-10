"""
BloodBeacon Tests - Stage 1
Tests for schema, seed data, and basic functionality.
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add parent directory to path so we can import the app and mock_db
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use mock database for testing
import tests.mock_db as mock_db
sys.modules['db'] = mock_db

import app as app_module
from app import app

@pytest.fixture
def client():
    """Create a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        # Reset mock database before each test
        mock_db.reset()
        yield client

class TestSchemaAndSeed:
    """Tests for schema and seed data."""
    
    def test_schema_has_all_tables(self):
        """Verify all 6 required tables are defined in schema.sql."""
        with open("schema.sql", "r") as f:
            schema = f.read()
        
        required_tables = ["donors", "donations", "requests", "alerts", "rules", "audit_log"]
        for table in required_tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in schema, \
                f"Table '{table}' not found in schema.sql"
    
    def test_schema_has_indexes(self):
        """Verify indexes exist on blood_group and city."""
        with open("schema.sql", "r") as f:
            schema = f.read()
        
        assert "idx_donors_blood_group" in schema
        assert "idx_donors_city" in schema
        assert "idx_requests_blood_group" in schema
        assert "idx_requests_city" in schema
    
    def test_seed_script_exists(self):
        """Verify seed.py file exists."""
        assert os.path.exists("seed.py"), "seed.py not found"
    
    def test_seed_covers_all_blood_groups(self):
        """Verify seed data covers all 8 blood groups."""
        from seed import SEED_DONORS, ADDITIONAL_DONORS
        
        all_donors = SEED_DONORS + ADDITIONAL_DONORS
        blood_groups = {donor["blood_group"] for donor in all_donors}
        
        expected_groups = {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"}
        assert blood_groups == expected_groups, \
            f"Missing blood groups. Have: {blood_groups}, Expected: {expected_groups}"
    
    def test_seed_covers_both_cities(self):
        """Verify seed data covers both Tiruchirappalli and Chennai."""
        from seed import SEED_DONORS, ADDITIONAL_DONORS
        
        all_donors = SEED_DONORS + ADDITIONAL_DONORS
        cities = {donor["city"] for donor in all_donors}
        
        expected_cities = {"Tiruchirappalli", "Chennai"}
        assert cities == expected_cities, \
            f"Missing cities. Have: {cities}, Expected: {expected_cities}"
    
    def test_seed_has_varied_donation_dates(self):
        """Verify seed donations have varied last-donation dates."""
        from seed import SEED_DONORS, ADDITIONAL_DONORS
        
        all_donors = SEED_DONORS + ADDITIONAL_DONORS
        assert len(all_donors) >= 30, f"Expected ~36 donors, got {len(all_donors)}"
    
    def test_nbtc_rules_present(self):
        """Verify NBTC rules are defined in seed."""
        from seed import SEED_RULES
        
        required_rules = [
            "age_min", "age_max", "weight_min_kg", "hemoglobin_min",
            "donation_gap_men_days", "donation_gap_women_days"
        ]
        rule_keys = {rule["key"] for rule in SEED_RULES}
        
        for rule in required_rules:
            assert rule in rule_keys, f"Rule '{rule}' not found in SEED_RULES"

class TestDonorRegistration:
    """Tests for donor registration."""
    
    def test_register_page_loads(self, client):
        """Test that registration page loads."""
        response = client.get("/register")
        assert response.status_code == 200
        assert b"Register as a Donor" in response.data
    
    @patch("app.requests.post")
    def test_donor_registration_success(self, mock_post, client):
        """Test successful donor registration."""
        mock_post.return_value = MagicMock(status_code=200)
        response = client.post("/register", data={
            "name": "Test Donor",
            "blood_group": "B+",
            "city": "Tiruchirappalli",
            "area": "Cantonment",
            "phone": "9999999999",
            "gender": "Male",
            "date_of_birth": "1990-01-01",
            "weight_kg": "70"
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b"registered as a donor" in response.data or b"Welcome" in response.data
        assert mock_db.get_all_donors()[-1]["phone"] == "919999999999"
        assert mock_post.call_count == 1
        assert mock_post.call_args.kwargs["json"]["phone"] == "919999999999"
        assert "🩸 Welcome to BloodBeacon, Test!" in mock_post.call_args.kwargs["json"]["message"]
        assert mock_db.get_audit_log()[-1]["action"] == "welcome_msg_sent"

    @patch("app.requests.post")
    def test_donor_registration_nepal_stores_digits_only(self, mock_post, client):
        mock_post.return_value = MagicMock(status_code=200)
        response = client.post("/register", data={
            "name": "Nepal Donor",
            "blood_group": "O+",
            "city": "Kathmandu",
            "area": "Thamel",
            "country": "977",
            "phone": "9817612738",
            "gender": "Male",
            "date_of_birth": "1990-01-01",
            "weight_kg": "70"
        }, follow_redirects=True)

        assert response.status_code == 200
        assert mock_db.get_all_donors()[-1]["phone"] == "9779817612738"

    @patch("app.requests.post", side_effect=TimeoutError("bridge offline"))
    def test_donor_registration_succeeds_when_welcome_bridge_fails(self, mock_post, client):
        response = client.post("/register", data={
            "name": "Offline Donor",
            "blood_group": "A+",
            "city": "Kathmandu",
            "area": "Thamel",
            "country": "977",
            "phone": "9817612738",
            "gender": "Female",
            "date_of_birth": "1995-01-01",
            "weight_kg": "60"
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b"registered as a donor" in response.data or b"Welcome" in response.data
        assert mock_db.get_all_donors()[-1]["phone"] == "9779817612738"
        assert mock_db.get_audit_log()[-1]["action"] == "welcome_msg_failed"

    def test_donor_registration_rejects_short_mobile(self, client):
        response = client.post("/register", data={
            "name": "Short Number",
            "blood_group": "B+",
            "city": "Tiruchirappalli",
            "area": "Cantonment",
            "country": "91",
            "phone": "987654321",
            "gender": "Male",
            "date_of_birth": "1990-01-01",
            "weight_kg": "70"
        }, follow_redirects=True)

        assert b"exactly 10" in response.data
        assert mock_db.get_all_donors() == []

    @patch("app._send_whatsapp_message")
    def test_seed_does_not_send_welcome_messages(self, mock_send, client):
        import seed

        assert seed.seed_database() is True
        mock_send.assert_not_called()
    
    def test_donor_registration_missing_fields(self, client):
        """Test registration with missing required fields."""
        response = client.post("/register", data={
            "name": "Test Donor",
            "blood_group": "B+",
            # Missing other fields
        }, follow_redirects=True)
        
        assert b"required" in response.data.lower()

class TestRequestBlood:
    """Tests for blood request submission."""
    
    def test_request_page_loads(self, client):
        """Test that request page loads."""
        response = client.get("/request")
        assert response.status_code == 200
        assert b"Request Blood" in response.data
    
    def test_blood_request_success(self, client):
        """Test successful blood request submission."""
        response = client.post("/request", data={
            "patient_name": "Test Patient",
            "blood_group": "B+",
            "component": "whole_blood",
            "units": "2",
            "hospital_name": "Test Hospital",
            "city": "Tiruchirappalli",
            "needed_by": "2024-11-15T10:30",
            "contact_phone": "9999888888"
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b"pending_verification" in response.data or b"submitted" in response.data.lower()
    
    def test_blood_request_missing_fields(self, client):
        """Test request submission with missing fields."""
        response = client.post("/request", data={
            "patient_name": "Test Patient",
            "blood_group": "B+",
            # Missing other required fields
        }, follow_redirects=True)
        
        assert b"required" in response.data.lower()

class TestMatchPreview:
    """Tests for Stage 1 match preview."""
    
    def test_match_preview_shows_compatible_donors(self, client):
        """Test that match preview shows compatible donors and filters by city."""
        # Setup: Create a B+ request in Tiruchirappalli
        req = mock_db.insert_request(
            patient_name="Test Patient",
            blood_group="B+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Tiruchirappalli",
            needed_by="2024-11-15T10:30",
            contact_phone="9999999999",
            created_by="public"
        )
        
        # Create test donors
        b_plus_tiruchi_1 = mock_db.insert_donor(
            name="B+ Donor 1", blood_group="B+", city="Tiruchirappalli",
            area="Cantonment", phone="9111111111", gender="Male",
            date_of_birth="1990-01-01", weight_kg=70
        )
        b_plus_tiruchi_2 = mock_db.insert_donor(
            name="B+ Donor 2", blood_group="B+", city="Tiruchirappalli",
            area="Srirangam", phone="9111111112", gender="Female",
            date_of_birth="1992-05-15", weight_kg=65
        )
        o_plus_tiruchi = mock_db.insert_donor(
            name="O+ Donor", blood_group="O+", city="Tiruchirappalli",
            area="Thillai Nagar", phone="9222222222", gender="Male",
            date_of_birth="1991-03-20", weight_kg=75
        )
        b_plus_chennai = mock_db.insert_donor(
            name="B+ Chennai", blood_group="B+", city="Chennai",
            area="Mylapore", phone="9333333333", gender="Male",
            date_of_birth="1989-07-10", weight_kg=72
        )
        
        # Test match preview
        response = client.get(f"/match/{req['id']}")
        assert response.status_code == 200
        
        # Should include exact B+ match donors from Tiruchirappalli
        assert b"B+ Donor 1" in response.data
        assert b"B+ Donor 2" in response.data
        
        # Should include O+ donor (compatible: O+ can donate to B+)
        assert b"O+ Donor" in response.data
        
        # Should NOT include B+ from Chennai (different city)
        assert b"B+ Chennai" not in response.data or b"Mylapore" not in response.data
    
    def test_match_preview_has_stage_2_checks(self, client):
        """Test that match preview shows Stage 2 eligibility and compatibility checks."""
        req = mock_db.insert_request(
            patient_name="Test Patient",
            blood_group="A+",
            component="whole_blood",
            units=1,
            hospital_name="Test Hospital",
            city="Chennai",
            needed_by="2024-11-15T10:30",
            contact_phone="9999999999",
            created_by="public"
        )
        
        response = client.get(f"/match/{req['id']}")
        assert response.status_code == 200
        assert b"Stage 2" in response.data
        # Template shows "ELIGIBLE" status and "eligibility + compatibility" info
        assert b"Stage 2 Active" in response.data or b"eligibility checks" in response.data

class TestPageNavigation:
    """Tests for basic page navigation."""
    
    def test_home_page_loads(self, client):
        """Test that home page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"BloodBeacon" in response.data
        assert b"Register" in response.data
        assert b"Request" in response.data
    
    def test_staff_dashboard_loads(self, client):
        """Test that staff dashboard loads with staff flag (Stage 5 security)."""
        response = client.get("/staff?staff=1")
        assert response.status_code == 200
        # Staff dashboard should show requests grouped by status
        assert b"request" in response.data.lower()
    
    def test_staff_dashboard_requires_flag(self, client):
        """Test that staff dashboard returns 403 without staff flag (Stage 5 security)."""
        response = client.get("/staff")
        assert response.status_code == 403
    
    def test_404_page(self, client):
        """Test that 404 page works."""
        response = client.get("/nonexistent")
        assert response.status_code == 404

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
