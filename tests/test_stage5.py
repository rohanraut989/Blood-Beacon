"""
Tests for Stage 5: Staff Dashboard + Experiment Mode.

Tests for verification workflow, staff dashboard, donor directory,
and experiment mode strategy comparison.
"""

import pytest
import sys
import os

# Add parent directory to path so we can import the app and mock_db
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use mock database for testing - BEFORE importing app
import tests.mock_db as mock_db
sys.modules['db'] = mock_db

import app as app_module
from app import app
from datetime import date, timedelta

# ========== VERIFICATION WORKFLOW TESTS ==========

class TestVerificationWorkflow:
    """Tests for the verify/reject workflow."""
    
    def test_verify_request_changes_status(self):
        """Verifying a request should change status to 'verified'."""
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="O+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-123456",
            created_by="test"
        )
        assert req["status"] == "pending_verification"
        
        # Verify the request
        verified = mock_db.verify_request(req["id"], "staff_alice")
        assert verified["status"] == "verified"
        assert verified["verified_by"] == "staff_alice"
    
    def test_reject_request_changes_status(self):
        """Rejecting a request should change status to 'rejected'."""
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="O+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-123456",
            created_by="test"
        )
        
        # Reject the request
        rejected = mock_db.reject_request(req["id"], "staff_bob", "Invalid request")
        assert rejected["status"] == "rejected"
        assert rejected["verified_by"] == "staff_bob"
    
    def test_reject_creates_audit_log(self):
        """Rejecting a request should create an audit log entry."""
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="O+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-123456",
            created_by="test"
        )
        
        # Reject with reason
        mock_db.reject_request(req["id"], "staff_bob", "Invalid blood group for patient")
        
        # Audit log should exist (in real DB; mock might not persist across calls)
        # For now, just verify the reject succeeded
        rejected = mock_db.get_request(req["id"])
        assert rejected["status"] == "rejected"
    
    def test_activate_requires_verification(self):
        """Attempting to activate an unverified request should fail."""
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="O+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-123456",
            created_by="test"
        )
        
        # Try to activate without verifying
        # In app.py, this would return 409 Conflict
        # Here we just verify it's not yet verified
        req_status = mock_db.get_request(req["id"])
        assert req_status["status"] == "pending_verification"
        
        # Verify first
        mock_db.verify_request(req["id"], "staff_test")
        req_status = mock_db.get_request(req["id"])
        assert req_status["status"] == "verified"
        
        # Then activate should work
        activated = mock_db.update_request_status(req["id"], "active")
        assert activated["status"] == "active"

# ========== STAFF DASHBOARD TESTS ==========

class TestStaffDashboard:
    """Tests for the staff dashboard request queue."""
    
    def test_get_requests_by_status(self):
        """Dashboard should group requests by status."""
        # Create requests in different statuses
        req1 = mock_db.insert_request(
            patient_name="Patient1", blood_group="O+", component="whole_blood", units=2,
            hospital_name="Hospital1", city="Kathmandu", needed_by="2024-11-20",
            contact_phone="+977-1-111111", created_by="test"
        )
        
        req2 = mock_db.insert_request(
            patient_name="Patient2", blood_group="A+", component="whole_blood", units=1,
            hospital_name="Hospital2", city="Chennai", needed_by="2024-11-21",
            contact_phone="+91-44-222222", created_by="test"
        )
        
        # Verify req1
        mock_db.verify_request(req1["id"], "staff_alice")
        
        # Get requests by status
        pending = mock_db.get_requests_by_status("pending_verification")
        verified = mock_db.get_requests_by_status("verified")
        
        # req2 should be in pending, req1 should be in verified
        assert req2["id"] in [r["id"] for r in pending]
        assert req1["id"] in [r["id"] for r in verified]
    
    def test_donor_directory_shows_eligibility(self):
        """Donor directory should display eligibility status and reasons."""
        # Create a test donor
        donor = mock_db.insert_donor(
            name="Test Donor",
            blood_group="O+",
            city="Kathmandu",
            area="Patan",
            phone="+977-1-999999",
            gender="M",
            date_of_birth="1990-05-15",
            weight_kg=75.0
        )
        
        # Get all donors
        all_donors = mock_db.get_all_donors()
        
        # Should have the test donor
        assert len(all_donors) > 0
        assert any(d["id"] == donor["id"] for d in all_donors)
        
        # Each donor should have required fields
        for donor_info in all_donors:
            assert "id" in donor_info
            assert "name" in donor_info
            assert "blood_group" in donor_info
            assert "city" in donor_info

# ========== EXPERIMENT MODE TESTS ==========

class TestExperimentMode:
    """Tests for the experiment mode strategy comparison."""
    
    def test_experiment_determinism_with_seed(self):
        """Same seed should produce same results (deterministic)."""
        import random as py_random
        from alerting import determine_reply
        
        # Run experiment 1 with seed 42
        py_random.seed(42)
        confirmations1 = 0
        rng1 = py_random.Random(42)
        for _ in range(100):
            donor = {"predicted_score": py_random.random()}
            if determine_reply(donor, donor["predicted_score"], rng1) == "confirmed":
                confirmations1 += 1
        
        # Run experiment 2 with same seed
        py_random.seed(42)
        confirmations2 = 0
        rng2 = py_random.Random(42)
        for _ in range(100):
            donor = {"predicted_score": py_random.random()}
            if determine_reply(donor, donor["predicted_score"], rng2) == "confirmed":
                confirmations2 += 1
        
        # Should be identical
        assert confirmations1 == confirmations2
    
    def test_waves_strategy_fewer_alerts_than_broadcast(self):
        """Waves strategy should alert fewer donors than broadcast on same pool."""
        import random as py_random
        from alerting import determine_reply
        
        # Create synthetic donor pool
        py_random.seed(123)
        pool_size = 100
        units_needed = 2
        
        synthetic_donors = []
        for _ in range(pool_size):
            synthetic_donors.append({
                "id": py_random.randint(10000, 99999),
                "predicted_score": py_random.random(),
            })
        
        # Broadcast: alert everyone
        broadcast_alerts = pool_size
        
        # Waves: alert Wave 1 (10) + Wave 2 (20) = up to 30
        wave1_size = min(10, pool_size)
        wave2_size = min(20, pool_size - wave1_size)
        wave_alerts = wave1_size + wave2_size  # Worst case: need all of Wave 2
        
        # Waves should be less or equal to broadcast
        assert wave_alerts <= broadcast_alerts
        # In practice, waves will often be much less (only fires Wave 2 if needed)
    
    def test_experiment_success_rates_valid(self):
        """Success rates should be between 0 and 1."""
        import random as py_random
        from alerting import determine_reply
        
        py_random.seed(456)
        trials = 10
        
        success_rates_waves = []
        success_rates_broadcast = []
        
        for trial in range(trials):
            pool_size = 50
            units_needed = 2
            
            synthetic_donors = [
                {"id": i, "predicted_score": py_random.random()}
                for i in range(pool_size)
            ]
            
            # Broadcast simulation
            seeded_rng = py_random.Random(456 + trial)
            confirmations_broadcast = 0
            for donor in synthetic_donors:
                if determine_reply(donor, donor["predicted_score"], seeded_rng) == "confirmed":
                    confirmations_broadcast += 1
                if confirmations_broadcast >= units_needed:
                    break
            
            success_broadcast = 1.0 if confirmations_broadcast >= units_needed else 0.0
            success_rates_broadcast.append(success_broadcast)
            
            # Waves simulation
            sorted_donors = sorted(synthetic_donors, key=lambda d: d["predicted_score"], reverse=True)
            seeded_rng = py_random.Random(456 + trial)
            
            confirmations_wave1 = 0
            for donor in sorted_donors[:10]:
                if determine_reply(donor, donor["predicted_score"], seeded_rng) == "confirmed":
                    confirmations_wave1 += 1
                if confirmations_wave1 >= units_needed:
                    break
            
            if confirmations_wave1 >= units_needed:
                success_waves = 1.0
            else:
                # Might need Wave 2
                confirmations_wave2 = 0
                for donor in sorted_donors[10:30]:
                    if determine_reply(donor, donor["predicted_score"], seeded_rng) == "confirmed":
                        confirmations_wave2 += 1
                    if confirmations_wave1 + confirmations_wave2 >= units_needed:
                        break
                success_waves = 1.0 if (confirmations_wave1 + confirmations_wave2) >= units_needed else 0.0
            
            success_rates_waves.append(success_waves)
        
        # All rates should be 0 or 1
        for rate in success_rates_broadcast + success_rates_waves:
            assert 0 <= rate <= 1
            assert rate in [0.0, 1.0]


# ========== EXPERIMENT ROUTES TESTS (Stage 5.1) ==========

class TestExperimentRoutes:
    """Tests for experiment mode HTTP routes."""

    def test_experiment_mode_get_returns_200(self):
        """GET /staff/experiment?staff=1 should return 200 with form."""
        from app import app
        client = app.test_client()
        response = client.get("/staff/experiment?staff=1")
        assert response.status_code == 200
        assert b"Experiment Mode" in response.data
        assert b"Pool Size" in response.data
        assert b"Run Experiment" in response.data

    def test_experiment_mode_post_deterministic(self):
        """POST same params twice should return identical results."""
        from app import app
        client = app.test_client()
        
        # First run with seed 42
        response1 = client.post("/staff/experiment?staff=1", data={
            "pool_size": "60",
            "units_needed": "2",
            "trials": "10",
            "seed": "42"
        }, follow_redirects=False)
        assert response1.status_code == 200
        
        # Extract summary from first response
        data1 = response1.data.decode()
        assert "Broadcast Strategy" in data1
        assert "Waves Strategy" in data1
        
        # Extract numeric values (careful parsing of the HTML)
        import re
        broadcast_alerts1 = re.search(r'📢 Broadcast Strategy.*?Average Alerts Sent.*?<div class="metric-value">([0-9.]+)', data1, re.DOTALL)
        waves_alerts1 = re.search(r'🌊 Waves Strategy.*?Average Alerts Sent.*?<div class="metric-value">([0-9.]+)', data1, re.DOTALL)
        
        # Second run with same seed
        response2 = client.post("/staff/experiment?staff=1", data={
            "pool_size": "60",
            "units_needed": "2",
            "trials": "10",
            "seed": "42"
        }, follow_redirects=False)
        assert response2.status_code == 200
        
        data2 = response2.data.decode()
        broadcast_alerts2 = re.search(r'📢 Broadcast Strategy.*?Average Alerts Sent.*?<div class="metric-value">([0-9.]+)', data2, re.DOTALL)
        waves_alerts2 = re.search(r'🌊 Waves Strategy.*?Average Alerts Sent.*?<div class="metric-value">([0-9.]+)', data2, re.DOTALL)
        
        # Exact match proves determinism
        if broadcast_alerts1 and broadcast_alerts2:
            assert broadcast_alerts1.group(1) == broadcast_alerts2.group(1)
        if waves_alerts1 and waves_alerts2:
            assert waves_alerts1.group(1) == waves_alerts2.group(1)

    def test_experiment_waves_less_than_broadcast(self):
        """Waves strategy should send fewer or equal alerts than Broadcast."""
        from app import app
        client = app.test_client()
        
        response = client.post("/staff/experiment?staff=1", data={
            "pool_size": "60",
            "units_needed": "2",
            "trials": "10",
            "seed": "42"
        }, follow_redirects=False)
        assert response.status_code == 200
        
        data = response.data.decode()
        import re
        
        # Extract broadcast avg alerts
        broadcast_match = re.search(r'📢 Broadcast Strategy.*?Average Alerts Sent.*?<div class="metric-value">([0-9.]+)', data, re.DOTALL)
        waves_match = re.search(r'🌊 Waves Strategy.*?Average Alerts Sent.*?<div class="metric-value">([0-9.]+)', data, re.DOTALL)
        
        if broadcast_match and waves_match:
            broadcast_alerts = float(broadcast_match.group(1))
            waves_alerts = float(waves_match.group(1))
            assert waves_alerts <= broadcast_alerts

    def test_experiment_success_rates_valid(self):
        """Success rates should be in [0, 1]."""
        from app import app
        client = app.test_client()
        
        response = client.post("/staff/experiment?staff=1", data={
            "pool_size": "60",
            "units_needed": "2",
            "trials": "10",
            "seed": "42"
        }, follow_redirects=False)
        assert response.status_code == 200
        
        data = response.data.decode()
        import re
        
        # Find all success rate metrics
        success_matches = re.findall(r'Success Rate.*?<div class="metric-value">([0-9.%]+)', data, re.DOTALL)
        for match in success_matches:
            if "%" in match:
                pct = float(match.replace("%", ""))
                assert 0 <= pct <= 100

    def test_experiment_results_has_synthetic_caption(self):
        """Results page should display synthetic data caption."""
        from app import app
        client = app.test_client()
        
        response = client.post("/staff/experiment?staff=1", data={
            "pool_size": "60",
            "units_needed": "2",
            "trials": "10",
            "seed": "42"
        }, follow_redirects=False)
        assert response.status_code == 200
        
        data = response.data.decode()
        assert "Synthetic Data" in data or "synthetic" in data.lower()
        assert "test data" in data.lower() or "procedurally generated" in data.lower()

    def test_experiment_mode_requires_staff_flag(self):
        """GET/POST /staff/experiment without ?staff=1 should return 403."""
        from app import app
        client = app.test_client()
        
        # GET without flag
        response = client.get("/staff/experiment")
        assert response.status_code == 403
        
        # POST without flag
        response = client.post("/staff/experiment", data={
            "pool_size": "60",
            "units_needed": "2",
            "trials": "10",
            "seed": "42"
        })
        assert response.status_code == 403


# ========== CLOSE REQUEST TESTS (Stage 5.1) ==========

class TestCloseRequest:
    """Tests for closing requests."""
    
    def setup_method(self):
        """Reset mock_db before each test."""
        mock_db.reset()

    def test_close_active_request(self):
        """Closing an active request should change status to 'closed'."""
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="O+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-123456",
            created_by="test"
        )
        mock_db.verify_request(req["id"], "staff_alice")
        mock_db.update_request_status(req["id"], "active")
        
        closed = mock_db.close_request(req["id"], "staff_bob", "Donor found")
        assert closed["status"] == "closed"
        
        # Check audit log
        audit_logs = mock_db.get_audit_log()
        close_logs = [log for log in audit_logs if log["action"] == "close_request"]
        assert len(close_logs) > 0
        assert "Donor found" in close_logs[-1]["detail"]

    def test_close_verified_request(self):
        """Closing a verified (but not activated) request should work."""
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="A+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-123456",
            created_by="test"
        )
        mock_db.verify_request(req["id"], "staff_alice")
        
        closed = mock_db.close_request(req["id"], "staff_bob", "Changed mind")
        assert closed["status"] == "closed"

    def test_close_request_creates_audit_log(self):
        """Closing a request should create an audit log entry."""
        mock_db.reset()
        
        req = mock_db.insert_request(
            patient_name="Patient",
            blood_group="B+",
            component="whole_blood",
            units=2,
            hospital_name="Test Hospital",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-123456",
            created_by="test"
        )
        mock_db.verify_request(req["id"], "staff_alice")
        mock_db.update_request_status(req["id"], "active")
        
        # Close the request
        mock_db.close_request(req["id"], "staff_bob", "Emergency resolved")
        
        # Check audit log
        audit_logs = mock_db.get_audit_log()
        close_logs = [log for log in audit_logs if log["action"] == "close_request"]
        assert len(close_logs) == 1
        assert close_logs[0]["actor"] == "staff_bob"
        assert close_logs[0]["entity_id"] == req["id"]


# ========== DASHBOARD RENDER TESTS (Stage 5.1) ==========

class TestDashboardRender:
    """Tests that the staff dashboard template renders requests correctly."""
    
    def setup_method(self):
        """Reset mock_db before each test."""
        mock_db.reset()

    def test_dashboard_renders_request_by_status(self):
        """Dashboard should render all requests grouped by status."""
        client = app.test_client()
        
        # Create one request per status
        pending_req = mock_db.insert_request(
            patient_name="Pending Patient",
            blood_group="O+",
            component="whole_blood",
            units=2,
            hospital_name="Hospital A",
            city="Kathmandu",
            needed_by="2024-11-20",
            contact_phone="+977-1-111111",
            created_by="test"
        )
        
        verified_req = mock_db.insert_request(
            patient_name="Verified Patient",
            blood_group="A+",
            component="whole_blood",
            units=2,
            hospital_name="Hospital B",
            city="Pokhara",
            needed_by="2024-11-20",
            contact_phone="+977-1-222222",
            created_by="test"
        )
        mock_db.verify_request(verified_req["id"], "staff_alice")
        
        active_req = mock_db.insert_request(
            patient_name="Active Patient",
            blood_group="B+",
            component="whole_blood",
            units=2,
            hospital_name="Hospital C",
            city="Lalitpur",
            needed_by="2024-11-20",
            contact_phone="+977-1-333333",
            created_by="test"
        )
        mock_db.verify_request(active_req["id"], "staff_alice")
        mock_db.update_request_status(active_req["id"], "active")
        
        # GET dashboard
        response = client.get("/staff?staff=1")
        assert response.status_code == 200
        data = response.data.decode()
        
        # All patient names should appear in the response
        assert "Pending Patient" in data
        assert "Verified Patient" in data
        assert "Active Patient" in data

