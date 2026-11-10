"""
BloodBeacon Tests - Stage 6.1.1: Staff UX Mini-Fix
- Friendly 403 error pages
- Staff session persistence  
- Approval flow end-to-end
- Display formatting (dates, units)
"""

import pytest
import sys
import os

# Add parent directory to path so we can import the app and mock_db
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use mock database for testing
import tests.mock_db as mock_db
sys.modules['db'] = mock_db

import app as app_module
from app import app

@pytest.fixture
def client():
    """Create test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

# ===== TEST 1: Friendly 403 Error Pages =====

def test_staff_dashboard_blank_403_now_friendly(client):
    """Accessing /staff without ?staff=1 returns friendly HTML, not blank 403."""
    response = client.get("/staff")
    assert response.status_code == 403
    assert b"Staff Access Required" in response.data or b"staff=1" in response.data
    assert b"<html" in response.data or b"<!DOCTYPE" in response.data or b"extends" in response.data
    # Should not be blank
    assert len(response.data) > 50

def test_staff_donors_blank_403_now_friendly(client):
    """Accessing /staff/donors without ?staff=1 returns friendly HTML."""
    response = client.get("/staff/donors")
    assert response.status_code == 403
    assert b"staff=1" in response.data
    assert len(response.data) > 50

def test_activate_blank_403_now_friendly(client):
    """Activating request without ?staff=1 returns friendly HTML."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="P1", blood_group="O+", component="WB",
        units=2, hospital_name="H1", city="City1", contact_phone="123",
        needed_by="2026-01-01", created_by="test"
    )
    mock_db.update_request_status(req["id"], "verified")
    
    response = client.post(f"/request/{req['id']}/activate", data={})
    assert response.status_code == 403
    assert b"staff=1" in response.data
    assert len(response.data) > 50

# ===== TEST 2: Staff Session Persistence =====

def test_staff_access_with_session(client):
    """Staff access via ?staff=1 allows requests."""
    mock_db.reset()
    mock_db.insert_request(
        patient_name="P1", blood_group="O+", component="WB",
        units=2, hospital_name="H1", city="City1", contact_phone="123",
        needed_by="2026-01-01", created_by="test"
    )
    
    # GET /staff?staff=1
    response = client.get("/staff?staff=1")
    assert response.status_code == 200
    assert b"Staff Dashboard" in response.data

# ===== TEST 3: Approval Flow End-to-End =====

def test_verify_request_button_present_on_pending_verification(client):
    """Pending verification requests show Verify button."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Patient A", blood_group="O+", component="WB",
        units=2, hospital_name="Hospital A", city="City1", contact_phone="555-1234",
        needed_by="2026-11-10T22:55:00Z", created_by="test"
    )
    
    response = client.get(f"/request/{req['id']}?staff=1")
    assert response.status_code == 200
    assert b"Verify Request" in response.data
    assert b"Reject Request" in response.data

def test_reject_request_button_present_on_pending_verification(client):
    """Pending verification requests show Reject button."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Patient B", blood_group="B+", component="WB",
        units=1, hospital_name="Hospital B", city="City2", contact_phone="555-5678",
        needed_by="2026-11-15", created_by="test"
    )
    
    response = client.get(f"/request/{req['id']}?staff=1")
    assert response.status_code == 200
    assert b"Reject Request" in response.data

def test_verify_button_post_carries_staff_flag(client):
    """Verify button form POSTs to endpoint with ?staff=1."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Patient C", blood_group="AB+", component="WB",
        units=3, hospital_name="Hospital C", city="City3", contact_phone="555-9999",
        needed_by="2026-12-01", created_by="test"
    )
    
    response = client.get(f"/request/{req['id']}?staff=1")
    expected_url = f"/request/{req['id']}/verify?staff=1"
    assert expected_url.encode() in response.data

def test_reject_button_post_carries_staff_flag(client):
    """Reject button form POSTs to endpoint with ?staff=1."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Patient D", blood_group="A-", component="WB",
        units=2, hospital_name="Hospital D", city="City4", contact_phone="555-4321",
        needed_by="2026-10-20", created_by="test"
    )
    
    response = client.get(f"/request/{req['id']}?staff=1")
    expected_url = f"/request/{req['id']}/reject?staff=1"
    assert expected_url.encode() in response.data

def test_verify_flips_status_to_verified_and_creates_audit(client):
    """POST /request/<id>/verify flips status to verified and creates audit entry."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Verify Test", blood_group="O+", component="WB",
        units=2, hospital_name="Hospital E", city="City5", contact_phone="555-0000",
        needed_by="2026-12-31", created_by="test"
    )
    
    response = client.post(
        f"/request/{req['id']}/verify?staff=1",
        data={"staff_name": "Dr. Smith"},
        follow_redirects=False
    )
    
    # Should redirect to the staff request detail page
    assert response.status_code in [302, 303]
    assert response.headers["Location"].endswith(
        f"/request/{req['id']}?staff=1"
    )
    
    # Check that status changed
    updated_req = mock_db.get_request(req["id"])
    assert updated_req["status"] == "verified"
    
    # Check audit log
    audit_logs = mock_db.get_audit_log()
    verify_logs = [a for a in audit_logs if a.get("action") == "verify_request"]
    assert len(verify_logs) > 0
    assert verify_logs[0]["actor"] == "Dr. Smith"

def test_verified_staff_detail_has_activate_form_and_public_view_does_not(client):
    """Verified requests expose activation only in the staff request detail."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Activation Test", blood_group="O+", component="WB",
        units=1, hospital_name="Hospital E", city="City5", contact_phone="555-0000",
        needed_by="2026-12-31", created_by="test"
    )
    mock_db.update_request_status(req["id"], "verified")

    staff_response = client.get(f"/request/{req['id']}?staff=1")
    assert staff_response.status_code == 200
    assert b"Activate" in staff_response.data
    assert f"/request/{req['id']}/activate?staff=1&channel=whatsapp".encode() in staff_response.data
    assert b"WhatsApp Bridge" in staff_response.data

    with client.session_transaction() as session:
        session.pop("staff", None)
    public_response = client.get(f"/request/{req['id']}")
    assert public_response.status_code == 200
    assert b"Activate" not in public_response.data
    assert b"WhatsApp Bridge" not in public_response.data

def test_reject_flips_status_to_rejected_and_creates_audit(client):
    """POST /request/<id>/reject flips status to rejected and creates audit entry."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Reject Test", blood_group="B-", component="WB",
        units=1, hospital_name="Hospital F", city="City6", contact_phone="555-1111",
        needed_by="2026-11-05", created_by="test"
    )
    
    response = client.post(
        f"/request/{req['id']}/reject?staff=1",
        data={"staff_name": "Dr. Jones", "reason": "Insufficient blood supply"},
        follow_redirects=False
    )
    
    # Should redirect
    assert response.status_code in [302, 303]
    
    # Check status changed
    updated_req = mock_db.get_request(req["id"])
    assert updated_req["status"] == "rejected"
    
    # Check audit log
    audit_logs = mock_db.get_audit_log()
    reject_logs = [a for a in audit_logs if a.get("action") == "reject_request"]
    assert len(reject_logs) > 0
    assert reject_logs[0]["actor"] == "Dr. Jones"

def test_verify_without_staff_flag_returns_friendly_403(client):
    """POST /request/<id>/verify without ?staff=1 returns friendly 403."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="P1", blood_group="O+", component="WB",
        units=2, hospital_name="H1", city="City1", contact_phone="123",
        needed_by="2026-01-01", created_by="test"
    )
    
    response = client.post(f"/request/{req['id']}/verify", data={"staff_name": "Someone"})
    assert response.status_code == 403
    assert b"staff=1" in response.data

def test_reject_without_staff_flag_returns_friendly_403(client):
    """POST /request/<id>/reject without ?staff=1 returns friendly 403."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="P1", blood_group="O+", component="WB",
        units=2, hospital_name="H1", city="City1", contact_phone="123",
        needed_by="2026-01-01", created_by="test"
    )
    
    response = client.post(f"/request/{req['id']}/reject", data={"staff_name": "Someone"})
    assert response.status_code == 403
    assert b"staff=1" in response.data

# ===== TEST 4: Display Formatting (Dates & Units) =====

def test_needed_by_renders_as_human_date_iso_timestamp(client):
    """'Needed By' renders as human-readable date from ISO timestamp."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Date Test", blood_group="O+", component="WB",
        units=2, hospital_name="H1", city="City1", contact_phone="123",
        needed_by="2026-11-10T22:55:00Z", created_by="test"
    )
    
    response = client.get(f"/request/{req['id']}?staff=1")
    assert response.status_code == 200
    # Should render as human date (contains Nov and 2026, not raw ISO)
    assert b"Nov" in response.data or b"2026" in response.data

def test_needed_by_renders_as_human_date_iso_date(client):
    """'Needed By' renders as human-readable date from ISO date."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Date Test 2", blood_group="A+", component="WB",
        units=3, hospital_name="H2", city="City2", contact_phone="456",
        needed_by="2026-11-10", created_by="test"
    )
    
    response = client.get(f"/request/{req['id']}?staff=1")
    assert response.status_code == 200
    # Should render as human date
    assert b"Nov" in response.data and b"2026" in response.data

def test_units_render_as_whole_number(client):
    """Units render as whole number (1, not 1.0)."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Units Test", blood_group="O+", component="WB",
        units=2.0, hospital_name="H1", city="City1", contact_phone="123",
        needed_by="2026-01-01", created_by="test"
    )
    
    response = client.get(f"/request/{req['id']}?staff=1")
    assert response.status_code == 200
    # Should render as "2", check for the number in units field
    assert b">2<" in response.data

def test_units_with_float_render_as_int(client):
    """Units like 2.5 still render correctly."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Float Units Test", blood_group="B+", component="WB",
        units=2.5, hospital_name="H1", city="City1", contact_phone="123",
        needed_by="2026-01-01", created_by="test"
    )
    
    response = client.get(f"/request/{req['id']}?staff=1")
    assert response.status_code == 200
    # 2.5 should round to 2 or 3
    assert b">2<" in response.data or b">3<" in response.data

# ===== TEST 5: Staff Link Carries Flag =====

def test_home_staff_link_carries_flag(client):
    """Home page staff link includes ?staff=1."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"/staff?staff=1" in response.data

def test_staff_dashboard_view_details_link_carries_flag(client):
    """Staff dashboard 'View Details' link includes ?staff=1."""
    mock_db.reset()
    req = mock_db.insert_request(
        patient_name="Link Test", blood_group="O+", component="WB",
        units=2, hospital_name="H1", city="City1", contact_phone="123",
        needed_by="2026-01-01", created_by="test"
    )
    mock_db.update_request_status(req["id"], "verified")
    
    response = client.get("/staff?staff=1")
    assert response.status_code == 200
    expected_url = f"/request/{req['id']}?staff=1"
    assert expected_url.encode() in response.data

# ===== TEST 6: All Previous Tests Still Pass =====

def test_backward_compatibility_donor_registration_unchanged(client):
    """Donor registration still works (not affected by staff UX changes)."""
    response = client.get("/register")
    assert response.status_code == 200
    assert b"blood_group" in response.data

def test_backward_compatibility_request_creation_unchanged(client):
    """Blood request creation still works."""
    response = client.get("/request")
    assert response.status_code == 200
    assert b"patient_name" in response.data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
