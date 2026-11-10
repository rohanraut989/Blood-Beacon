"""
Mock database for testing (no live Supabase connection).
Used by tests to verify logic without database credentials.
"""

# In-memory test database
_test_donors = {}
_test_donations = {}
_test_requests = {}
_test_rules = {}
_test_audit_log = {}
_test_staff = {}

_id_counter = {"donors": 0, "donations": 0, "requests": 0, "rules": 0, "audit_log": 0, "alerts": 0}

def reset():
    """Clear all test data."""
    global _test_donors, _test_donations, _test_requests, _test_rules, _test_audit_log, _test_alerts, _test_staff, _id_counter
    _test_donors = {}
    _test_donations = {}
    _test_requests = {}
    _test_rules = {}
    _test_audit_log = {}
    _test_alerts = {}
    _test_staff = {}
    _id_counter = {"donors": 0, "donations": 0, "requests": 0, "rules": 0, "audit_log": 0, "alerts": 0}

def is_db_configured():
    return True

# === DONORS ===

def insert_donor(name, blood_group, city, area, phone, gender, date_of_birth, weight_kg):
    _id_counter["donors"] += 1
    donor = {
        "id": _id_counter["donors"],
        "name": name,
        "blood_group": blood_group,
        "city": city,
        "area": area,
        "phone": phone,
        "gender": gender,
        "date_of_birth": date_of_birth,
        "weight_kg": weight_kg,
        "created_at": "2024-01-01T00:00:00Z"
    }
    _test_donors[donor["id"]] = donor
    return donor

def get_donor_by_phone(phone):
    for donor in _test_donors.values():
        if donor["phone"] == phone:
            return donor
    return None

def get_donor(donor_id):
    return _test_donors.get(donor_id)

def get_donors_by_group_and_city(blood_group, city):
    return [d for d in _test_donors.values() if d["blood_group"] == blood_group and d["city"] == city]

def get_donors_by_city(city):
    return [d for d in _test_donors.values() if d["city"] == city]

def get_all_donors():
    """Get all donors."""
    return list(_test_donors.values())

# === REQUESTS ===

def insert_request(patient_name, blood_group, component, units, hospital_name, city, needed_by, contact_phone, created_by):
    _id_counter["requests"] += 1
    request = {
        "id": _id_counter["requests"],
        "patient_name": patient_name,
        "blood_group": blood_group,
        "component": component,
        "units": units,
        "hospital_name": hospital_name,
        "city": city,
        "needed_by": needed_by,
        "contact_phone": contact_phone,
        "status": "pending_verification",
        "created_by": created_by,
        "verified_by": None,
        "created_at": "2024-01-01T00:00:00Z"
    }
    _test_requests[request["id"]] = request
    return request

def get_request(request_id):
    return _test_requests.get(request_id)

def get_all_requests():
    return sorted(_test_requests.values(), key=lambda r: r["created_at"], reverse=True)

# === DONATIONS ===

def insert_donation(donor_id, donated_on, units, request_id=None, source="self_report"):
    _id_counter["donations"] += 1
    donation = {
        "id": _id_counter["donations"],
        "donor_id": donor_id,
        "donated_on": donated_on,
        "units": units,
        "request_id": request_id,
        "source": source,
        "created_at": "2024-01-01T00:00:00Z"
    }
    _test_donations[donation["id"]] = donation
    return donation

def get_donations_for_donor(donor_id):
    return sorted(
        [d for d in _test_donations.values() if d["donor_id"] == donor_id],
        key=lambda d: d["donated_on"],
        reverse=True
    )

# === RULES ===

def insert_rule(key, value, description=None):
    if key in _test_rules:
        _test_rules[key]["value"] = value
        _test_rules[key]["description"] = description
        return _test_rules[key]
    else:
        _id_counter["rules"] += 1
        rule = {
            "id": _id_counter["rules"],
            "key": key,
            "value": value,
            "description": description,
            "updated_at": "2024-01-01T00:00:00Z"
        }
        _test_rules[key] = rule
        return rule

def get_rule(key):
    return _test_rules.get(key)

def get_all_rules():
    return list(_test_rules.values())

# === AUDIT LOG ===

def insert_audit_log(actor, action, entity, entity_id=None, detail=None):
    _id_counter["audit_log"] += 1
    log_entry = {
        "id": _id_counter["audit_log"],
        "actor": actor,
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "detail": detail,
        "created_at": "2024-01-01T00:00:00Z"
    }
    _test_audit_log[log_entry["id"]] = log_entry
    return log_entry

def get_audit_log():
    """Get all audit log entries."""
    return list(_test_audit_log.values())

# === ALERTS (Stage 3+) ===

def get_alerts_for_donor(donor_id):
    """Get all alerts for a donor."""
    return [a for a in _test_alerts.values() if a["donor_id"] == donor_id]

# === ALERTS (Stage 4+) ===

_test_alerts = {}

def insert_alert(request_id, donor_id, wave_no, channel):
    """Insert an alert for a request."""
    _id_counter["alerts"] = _id_counter.get("alerts", 0) + 1
    alert = {
        "id": _id_counter["alerts"],
        "request_id": request_id,
        "donor_id": donor_id,
        "wave_no": wave_no,
        "channel": channel,
        "sent_at": "2024-01-01T00:00:00Z",
        "stage": "awaiting_recency",
        "reply": None,
        "message_id": None,
        "replied_at": None,
        "showed_up": None,
        "created_at": "2024-01-01",  # Date format only for alerting.py parsing
    }
    _test_alerts[alert["id"]] = alert
    return alert

def get_alerts_for_request(request_id):
    """Get all alerts for a request."""
    return [a for a in _test_alerts.values() if a["request_id"] == request_id]

def update_alert_reply(alert_id, reply, message_id=None, stage="done"):
    """Update an alert with a donor's reply."""
    if alert_id in _test_alerts:
        _test_alerts[alert_id]["reply"] = reply
        _test_alerts[alert_id]["stage"] = stage
        _test_alerts[alert_id]["replied_at"] = "2024-01-01T00:00:00Z"
        if message_id:
            _test_alerts[alert_id]["message_id"] = message_id
        return _test_alerts[alert_id]
    return None

def update_alert_stage(alert_id, stage, message_id=None):
    """Advance an alert conversation without recording a final reply."""
    if alert_id in _test_alerts:
        _test_alerts[alert_id]["stage"] = stage
        if message_id:
            _test_alerts[alert_id]["message_id"] = message_id
        return _test_alerts[alert_id]
    return None

def update_alert_showup(alert_id, showed_up):
    """Mark an alert as showed_up."""
    if alert_id in _test_alerts:
        _test_alerts[alert_id]["showed_up"] = showed_up
        return _test_alerts[alert_id]
    return None

# === REQUEST STATUS UPDATES (Stage 5+) ===

def update_request_status(request_id, new_status, verified_by=None):
    """Update a request status."""
    if request_id in _test_requests:
        _test_requests[request_id]["status"] = new_status
        if verified_by:
            _test_requests[request_id]["verified_by"] = verified_by
        return _test_requests[request_id]
    return None

def verify_request(request_id, staff_name):
    """Verify a request."""
    return update_request_status(request_id, "verified", staff_name)

def reject_request(request_id, staff_name, reason=None):
    """Reject a request."""
    result = update_request_status(request_id, "rejected", staff_name)
    if result:
        # Also log it
        insert_audit_log(
            actor=staff_name,
            action="reject_request",
            entity="request",
            entity_id=request_id,
            detail=f"Rejected. Reason: {reason}" if reason else "Rejected"
        )
    return result

def get_requests_by_status(status):
    """Get all requests with a given status."""
    return [r for r in _test_requests.values() if r["status"] == status]

def close_request(request_id, staff_name, reason=None):
    """Close a request."""
    result = update_request_status(request_id, "closed", staff_name)
    if result:
        # Also log it
        insert_audit_log(
            actor=staff_name,
            action="close_request",
            entity="request",
            entity_id=request_id,
            detail=f"Closed. Reason: {reason}" if reason else "Closed"
        )
    return result

# === STAFF ===

def insert_staff(username, password):
    """Insert a staff member."""
    staff = {
        "username": username,
        "password": password,
        "created_at": "2024-01-01T00:00:00Z"
    }
    _test_staff[username] = staff
    return staff

def get_staff(username):
    """Get a staff member."""
    return _test_staff.get(username)
