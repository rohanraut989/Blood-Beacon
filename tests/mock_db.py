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

_id_counter = {"donors": 0, "donations": 0, "requests": 0, "rules": 0, "audit_log": 0}

def reset():
    """Clear all test data."""
    global _test_donors, _test_donations, _test_requests, _test_rules, _test_audit_log, _id_counter
    _test_donors = {}
    _test_donations = {}
    _test_requests = {}
    _test_rules = {}
    _test_audit_log = {}
    _id_counter = {"donors": 0, "donations": 0, "requests": 0, "rules": 0, "audit_log": 0}

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

# === ALERTS (Stage 3+) ===

def get_alerts_for_donor(donor_id):
    """Get all alerts for a donor (returns empty list if no alerts table)."""
    return []  # Mock: no alert history yet
