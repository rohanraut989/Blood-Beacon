"""
Database access module for BloodBeacon.
This is the ONLY module that talks to Supabase.
All database interactions go through this interface.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Initialize Supabase client (only if credentials are available)
_client = None

def get_db() -> Client:
    """Get or create the Supabase client."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "Supabase credentials not found. "
                "Please set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
            )
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client

def is_db_configured() -> bool:
    """Check if Supabase is configured."""
    return SUPABASE_URL is not None and SUPABASE_SERVICE_KEY is not None

# === DONORS ===

def insert_donor(name: str, blood_group: str, city: str, area: str, 
                phone: str, gender: str, date_of_birth: str, weight_kg: float) -> dict:
    """Insert a new donor. Returns the donor record."""
    db = get_db()
    result = db.table("donors").insert({
        "name": name,
        "blood_group": blood_group,
        "city": city,
        "area": area,
        "phone": phone,
        "gender": gender,
        "date_of_birth": date_of_birth,
        "weight_kg": weight_kg,
    }).execute()
    return result.data[0] if result.data else None

def get_donor_by_phone(phone: str) -> dict:
    """Get a donor by phone number."""
    db = get_db()
    result = db.table("donors").select("*").eq("phone", phone).execute()
    return result.data[0] if result.data else None

def get_donor(donor_id: int) -> dict:
    """Get a donor by ID."""
    db = get_db()
    result = db.table("donors").select("*").eq("id", donor_id).execute()
    return result.data[0] if result.data else None

def get_donors_by_group_and_city(blood_group: str, city: str) -> list:
    """Get all donors with a specific blood group in a city."""
    db = get_db()
    result = db.table("donors").select("*").eq("blood_group", blood_group).eq("city", city).execute()
    return result.data if result.data else []

def get_donors_by_city(city: str) -> list:
    """Get all donors in a city."""
    db = get_db()
    result = db.table("donors").select("*").eq("city", city).execute()
    return result.data if result.data else []

# === REQUESTS ===

def insert_request(patient_name: str, blood_group: str, component: str,
                  units: float, hospital_name: str, city: str, needed_by: str,
                  contact_phone: str, created_by: str) -> dict:
    """Insert a new blood request. Returns the request record."""
    db = get_db()
    result = db.table("requests").insert({
        "patient_name": patient_name,
        "blood_group": blood_group,
        "component": component,
        "units": units,
        "hospital_name": hospital_name,
        "city": city,
        "needed_by": needed_by,
        "contact_phone": contact_phone,
        "created_by": created_by,
        "status": "pending_verification",
    }).execute()
    return result.data[0] if result.data else None

def get_request(request_id: int) -> dict:
    """Get a request by ID."""
    db = get_db()
    result = db.table("requests").select("*").eq("id", request_id).execute()
    return result.data[0] if result.data else None

def get_all_requests() -> list:
    """Get all requests."""
    db = get_db()
    result = db.table("requests").select("*").order("created_at", desc=True).execute()
    return result.data if result.data else []

# === DONATIONS ===

def insert_donation(donor_id: int, donated_on: str, units: float, 
                   request_id: int = None, source: str = "self_report") -> dict:
    """Insert a donation record."""
    db = get_db()
    result = db.table("donations").insert({
        "donor_id": donor_id,
        "donated_on": donated_on,
        "units": units,
        "request_id": request_id,
        "source": source,
    }).execute()
    return result.data[0] if result.data else None

def get_donations_for_donor(donor_id: int) -> list:
    """Get all donations for a donor."""
    db = get_db()
    result = db.table("donations").select("*").eq("donor_id", donor_id).order("donated_on", desc=True).execute()
    return result.data if result.data else []

# === RULES ===

def insert_rule(key: str, value: str, description: str = None) -> dict:
    """Insert or update a rule."""
    db = get_db()
    # Try to update first
    result = db.table("rules").update({"value": value, "description": description}).eq("key", key).execute()
    if not result.data:
        # If no rows updated, insert new
        result = db.table("rules").insert({
            "key": key,
            "value": value,
            "description": description,
        }).execute()
    return result.data[0] if result.data else None

def get_rule(key: str) -> dict:
    """Get a rule by key."""
    db = get_db()
    result = db.table("rules").select("*").eq("key", key).execute()
    return result.data[0] if result.data else None

def get_all_rules() -> list:
    """Get all rules."""
    db = get_db()
    result = db.table("rules").select("*").execute()
    return result.data if result.data else []

# === AUDIT LOG ===

def insert_audit_log(actor: str, action: str, entity: str, entity_id: int = None, detail: str = None) -> dict:
    """Insert an audit log entry."""
    db = get_db()
    result = db.table("audit_log").insert({
        "actor": actor,
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "detail": detail,
    }).execute()
    return result.data[0] if result.data else None

# === ALERTS (Stage 3+) ===

def get_alerts_for_donor(donor_id: int) -> list:
    """Get all past alerts sent to a donor (for predictor features)."""
    try:
        db = get_db()
        result = db.table("alerts").select("*").eq("donor_id", donor_id).execute()
        return result.data if result.data else []
    except Exception:
        # Table may not exist yet in early stages
        return []
