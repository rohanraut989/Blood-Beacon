"""
BloodBeacon — Emergency Blood-Donor Activation System
Flask application
"""

import os
import random
import requests
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import db
import eligibility
import compatibility
import predictor
import alerting
from phone import normalize_phone
from utils import parse_date

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

PORT = int(os.getenv("PORT", 5001))

# === JINJA2 FILTERS ===

@app.template_filter('human_date')
def format_human_date(value):
    """Convert ISO date/timestamp to human-readable format (e.g., '10 Nov 2026, 10:55 PM')."""
    if not value:
        return ""
    try:
        if isinstance(value, str):
            if "T" in value:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            else:
                dt = parse_date(value)
        else:
            dt = value
        if isinstance(dt, datetime):
            return dt.strftime("%d %b %Y, %I:%M %p").lstrip("0").replace(" 0", " ")
        return dt.strftime("%d %b %Y").lstrip("0")
    except (ValueError, AttributeError):
        return value

@app.template_filter('unit_int')
def format_unit_int(value):
    """Format unit as whole number (1, not 1.0)."""
    if value is None:
        return ""
    try:
        return str(int(float(value)))
    except (ValueError, TypeError):
        return str(value)

# === STAFF SESSION MANAGEMENT ===

def is_staff():
    """Check if user has staff access via flag or session."""
    if request.args.get("staff") == "1":
        session["staff"] = True
        return True
    return session.get("staff", False)

def require_staff():
    """Return 403 with friendly message if not staff."""
    if not is_staff():
        return render_template("staff_required.html"), 403
    return None

# === HOME ===

@app.route("/")
def home():
    """Home page: intro to BloodBeacon with three doors."""
    return render_template("home.html")

# === DONOR REGISTRATION ===

@app.route("/register", methods=["GET", "POST"])
def register_donor():
    """Donor registration form."""
    if request.method == "POST":
        try:
            # Extract form data
            name = request.form.get("name", "").strip()
            blood_group = request.form.get("blood_group", "").strip()
            city = request.form.get("city", "").strip()
            area = request.form.get("area", "").strip()
            country = request.form.get("country", "91").strip()
            national_phone = request.form.get("phone", "").strip()
            gender = request.form.get("gender", "").strip()
            date_of_birth = request.form.get("date_of_birth", "").strip()
            weight_kg = float(request.form.get("weight_kg", 0))

            # Validate required fields
            if not all([name, blood_group, city, national_phone, gender, date_of_birth, weight_kg]):
                flash("All fields are required.", "error")
                return redirect(url_for("register_donor"))

            try:
                phone = normalize_phone(country, national_phone)
            except ValueError as error:
                flash(str(error), "error")
                return redirect(url_for("register_donor"))

            # Check if phone already exists
            if db.is_db_configured():
                existing = db.get_donor_by_phone(phone)
                if existing:
                    flash("This phone number is already registered.", "error")
                    return redirect(url_for("register_donor"))

                # Insert donor
                donor = db.insert_donor(
                    name=name,
                    blood_group=blood_group,
                    city=city,
                    area=area,
                    phone=phone,
                    gender=gender,
                    date_of_birth=date_of_birth,
                    weight_kg=weight_kg
                )
                try:
                    welcome_message = (
                        f"🩸 Welcome to BloodBeacon, {name.split()[0]}! Thank you for "
                        f"registering as a {blood_group} blood donor in {city}. If someone "
                        f"near you urgently needs your blood, we will message you on this "
                        f"number. Your one reply can save a life. ❤️"
                    )
                    welcome_sent = _send_whatsapp_message(phone, welcome_message)
                    db.insert_audit_log(
                        actor="system",
                        action="welcome_msg_sent" if welcome_sent else "welcome_msg_failed",
                        entity="donor",
                        entity_id=donor["id"],
                        detail="Registration welcome message delivered"
                        if welcome_sent else "Registration succeeded but bridge welcome message failed",
                    )
                except Exception as error:
                    print(f"Welcome message audit failed for donor {donor['id']}: {error}")
                flash(f"Welcome, {name}! You have been registered as a donor.", "success")
                return redirect(url_for("home"))
            else:
                flash("Database not configured. Registration data not saved.", "warning")
                return redirect(url_for("register_donor"))

        except Exception as e:
            flash(f"Error during registration: {str(e)}", "error")
            return redirect(url_for("register_donor"))

    return render_template("register.html")

# === REQUEST BLOOD ===

@app.route("/request", methods=["GET", "POST"])
def request_blood():
    """Request Blood page: public form to submit a blood request."""
    if request.method == "POST":
        try:
            patient_name = request.form.get("patient_name", "").strip()
            blood_group = request.form.get("blood_group", "").strip()
            component = request.form.get("component", "whole_blood")
            units = float(request.form.get("units", 1))
            hospital_name = request.form.get("hospital_name", "").strip()
            city = request.form.get("city", "").strip()
            needed_by = request.form.get("needed_by", "").strip()
            contact_phone = request.form.get("contact_phone", "").strip()

            # Validate required fields
            if not all([patient_name, blood_group, hospital_name, city, needed_by, contact_phone]):
                flash("All fields are required.", "error")
                return redirect(url_for("request_blood"))

            if db.is_db_configured():
                req = db.insert_request(
                    patient_name=patient_name,
                    blood_group=blood_group,
                    component=component,
                    units=units,
                    hospital_name=hospital_name,
                    city=city,
                    needed_by=needed_by,
                    contact_phone=contact_phone,
                    created_by="public"
                )
                flash(
                    f"Request submitted for {patient_name}. "
                    f"Status: Pending Verification (id: {req['id']})",
                    "success"
                )
                return redirect(url_for("request_status", request_id=req["id"]))
            else:
                flash("Database not configured. Request not saved.", "warning")
                return redirect(url_for("request_blood"))

        except Exception as e:
            flash(f"Error submitting request: {str(e)}", "error")
            return redirect(url_for("request_blood"))

    return render_template("request.html")

# === REQUEST STATUS ===

def _get_bridge_status():
    """Check the authenticated WhatsApp bridge status."""
    try:
        bridge_url = os.getenv("BRIDGE_URL", "http://127.0.0.1:3100")
        bridge_secret = os.getenv("BRIDGE_SECRET", "")
        response = requests.get(
            f"{bridge_url}/status",
            headers={"X-Bridge-Secret": bridge_secret},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            connected = data.get("connected", data.get("status") == "connected")
            return {
                "label": "connected" if connected else "not connected",
                "error": None if connected else data.get("error", "bridge is not connected"),
            }
        return {"label": "not connected", "error": f"bridge status HTTP {response.status_code}"}
    except Exception as error:
        return {"label": "not connected", "error": str(error)}


@app.route("/request/<int:request_id>")
def request_status(request_id):
    """Show the status of a blood request."""
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    req = db.get_request(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("home"))

    # Check if staff mode is enabled, also preserving a prior staff session.
    staff_mode = is_staff()
    
    # Get alerts for this request (if any)
    alerts = db.get_alerts_for_request(request_id)
    
    # Build alert details with donor info
    alert_details = []
    for alert in alerts:
        donor = db.get_donor(alert["donor_id"])
        alert_with_donor = dict(alert)
        alert_with_donor["donor"] = donor
        alert_details.append(alert_with_donor)

    wave_outcome = None
    if staff_mode:
        audit_logs = db.get_audit_logs_for_entity("request", request_id)
        activation = next(
            (entry for entry in audit_logs if entry.get("action") == "activate_request"),
            None,
        )
        wave_outcome = activation.get("detail") if activation else None
    
    # Get bridge status for staff view
    bridge_status = _get_bridge_status() if staff_mode else None

    return render_template(
        "request_status.html",
        request=req,
        is_staff=staff_mode,
        alerts=alert_details,
        bridge_status=bridge_status,
        wave_outcome=wave_outcome,
    )

# === STAGE 5 VERIFICATION WORKFLOW ===

@app.route("/request/<int:request_id>/verify", methods=["POST"])
def verify_request_route(request_id):
    """Verify a pending request (staff only)."""
    staff_check = require_staff()
    if staff_check:
        return staff_check
    
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    req = db.get_request(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("home"))
    
    if req["status"] != "pending_verification":
        flash("Only pending requests can be verified.", "error")
        return redirect(url_for("request_status", request_id=request_id, staff=1))
    
    staff_name = request.form.get("staff_name", "Unknown Staff")
    db.verify_request(request_id, staff_name)
    db.insert_audit_log(
        actor=staff_name,
        action="verify_request",
        entity="request",
        entity_id=request_id,
        detail="Request verified and ready for activation"
    )
    
    flash("Request verified successfully.", "success")
    return redirect(url_for("request_status", request_id=request_id, staff=1))

@app.route("/request/<int:request_id>/reject", methods=["POST"])
def reject_request_route(request_id):
    """Reject a pending request (staff only)."""
    staff_check = require_staff()
    if staff_check:
        return staff_check
    
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    req = db.get_request(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("home"))
    
    if req["status"] != "pending_verification":
        flash("Only pending requests can be rejected.", "error")
        return redirect(url_for("request_status", request_id=request_id, staff=1))
    
    staff_name = request.form.get("staff_name", "Unknown Staff")
    reason = request.form.get("reason", "No reason provided")
    db.reject_request(request_id, staff_name, reason)
    
    flash(f"Request rejected. Reason: {reason}", "info")
    return redirect(url_for("request_status", request_id=request_id, staff=1))

@app.route("/request/<int:request_id>/close", methods=["POST"])
def close_request_route(request_id):
    """Close an active or verified request (staff only)."""
    staff_check = require_staff()
    if staff_check:
        return staff_check
    
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    req = db.get_request(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("home"))
    
    # Can close active or verified requests
    if req["status"] not in ["active", "verified"]:
        flash(f"Can only close active or verified requests (current: {req['status']}).", "error")
        return redirect(url_for("request_status", request_id=request_id, staff=1))
    
    staff_name = request.form.get("staff_name", "Unknown Staff")
    reason = request.form.get("reason", "No reason provided")
    db.close_request(request_id, staff_name, reason)
    
    flash(f"Request closed. Reason: {reason}", "info")
    return redirect(url_for("request_status", request_id=request_id, staff=1))

@app.route("/request/<int:request_id>/activate", methods=["POST"])
def activate_request(request_id):
    """Activate a request and send Wave 1 alerts."""
    staff_check = require_staff()
    if staff_check:
        return staff_check
    
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    req = db.get_request(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("home"))
    
    # Only verified requests can be activated
    if req["status"] != "verified":
        if req["status"] == "pending_verification":
            return ("", 409)
        else:
            flash(f"Request cannot be activated (status: {req['status']}).", "error")
            return redirect(url_for("request_status", request_id=request_id, staff=1))
    
    # Get eligible donors and rank them
    all_donors = db.get_donors_by_city(req["city"])
    
    rules_list = db.get_all_rules()
    rules_dict = {r["key"]: r["value"] for r in rules_list}
    
    today = date.today()
    eligible_donors = []
    
    donations_by_donor = {}
    alerts_by_donor = {}
    
    for donor in all_donors:
        # Check blood type compatibility
        if not compatibility.is_compatible(donor["blood_group"], req["blood_group"], req.get("component", "whole_blood")):
            continue
        
        donations = db.get_donations_for_donor(donor["id"])
        donations_by_donor[donor["id"]] = donations
        alerts = db.get_alerts_for_donor(donor["id"])
        alerts_by_donor[donor["id"]] = alerts
        
        # Assess eligibility
        assessment = eligibility.assess_donor(donor, donations, rules_dict, today)
        
        donor_info = dict(donor)
        donor_info["eligibility_status"] = assessment["status"]
        
        if assessment["status"] == "eligible":
            eligible_donors.append(donor_info)
    
    # Rank eligible donors
    ranked_with_scores = predictor.rank_donors(
        req,
        eligible_donors,
        donations_by_donor,
        alerts_by_donor,
        today
    )
    
    # Convert to just donor dicts for planner
    ranked_donors = [donor for donor, score, reason in ranked_with_scores]
    
    # Plan waves
    now = datetime.now()
    plan = alerting.plan_waves(ranked_with_scores, req, alerts_by_donor, now)
    
    # Activate request
    db.update_request_status(request_id, "active")
    
    # Determine channel (whatsapp for real requests, simulator for testing)
    channel = request.args.get("channel", "whatsapp")  # Default to whatsapp
    
    # Write Wave 1 alerts and send messages
    wave1_donors = plan["wave1"]
    for donor in wave1_donors:
        db.insert_alert(
            request_id=request_id,
            donor_id=donor["id"],
            wave_no=1,
            channel=channel
        )
        
        # If WhatsApp channel, send message via bridge
        if channel == "whatsapp":
            _send_whatsapp_alert(donor, req)
    
    # Write audit log
    skip_counts = {}
    for skipped in plan["skipped"]:
        reason = skipped.get("reason", "unspecified reason")
        skip_counts[reason] = skip_counts.get(reason, 0) + 1
    skip_detail = ", ".join(
        f"{count} skipped ({reason})" for reason, count in skip_counts.items()
    )
    if not skip_detail:
        skip_detail = "0 skipped (no planner exclusions)"
    wave_detail = (
        f"Wave 1: {len(wave1_donors)} sent, {skip_detail}; "
        f"Wave 2: {len(plan['wave2'])} queued"
    )
    db.insert_audit_log(
        actor="staff_simulator",
        action="activate_request",
        entity="request",
        entity_id=request_id,
        detail=f"{wave_detail} on {channel}"
    )
    
    flash(f"Request activated! {len(wave1_donors)} donors alerted in Wave 1.", "success")
    return redirect(url_for("request_status", request_id=request_id, staff=1))


def _patient_first_name(req):
    """Return only the patient's first name for donor-facing messages."""
    return (req.get("patient_name") or "A patient").split()[0]

def _recency_message(req):
    return (
        f"{_patient_first_name(req)} needs {req.get('blood_group')} blood at "
        f"{req.get('hospital_name')}, {req.get('city')}. "
        "Did you donate blood in the last 3 months? Reply 1 = Yes, 2 = No"
    )

def _confirm_message(req):
    return (
        f"You can save a life today. Can you come to {req.get('hospital_name')} "
        f"to donate? Reply 1 = Yes, I can come, 2 = Not this time"
    )

def _receiver_details_message(donor, req):
    return (
        f"✅ Thank you, {donor.get('name', '').split()[0]}! You're confirmed to donate "
        f"{req.get('blood_group')} blood for {req.get('patient_name')} at "
        f"{req.get('hospital_name')}, {req.get('city')}. Receiver contact: "
        f"{req.get('patient_name')} — {req.get('contact_phone')}. Please call them "
        f"to coordinate. Needed by: {format_human_date(req.get('needed_by'))}."
    )

def _send_whatsapp_message(phone, message):
    """Send one donor-facing WhatsApp message through the bridge."""
    try:
        bridge_url = os.getenv("BRIDGE_URL", "http://127.0.0.1:3100")
        bridge_secret = os.getenv("BRIDGE_SECRET", "")
        response = requests.post(
            f"{bridge_url}/send",
            json={"phone": phone, "message": message},
            headers={"X-Bridge-Secret": bridge_secret},
            timeout=30
        )
        if response.status_code != 200:
            print(f"Failed to send WhatsApp message to {phone}: {response.status_code}")
            return False
        return True
    except Exception as e:
        print(f"Error sending WhatsApp message to {phone}: {e}")
        return False

def _send_whatsapp_alert(donor, req):
    """Send the first step of the donor conversation."""
    _send_whatsapp_message(donor["phone"], _recency_message(req))

# === STAGE 4 SIMULATOR ===

@app.route("/request/<int:request_id>/advance", methods=["POST"])
def advance_simulation(request_id):
    """Advance the simulator: process pending replies and fire Wave 2 if needed."""
    staff_check = require_staff()
    if staff_check:
        return staff_check
    
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    req = db.get_request(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("home"))
    
    # Get all alerts for this request
    alerts = db.get_alerts_for_request(request_id)
    
    # Separate by wave
    wave1_alerts = [a for a in alerts if a["wave_no"] == 1]
    wave2_alerts = [a for a in alerts if a["wave_no"] == 2]
    
    # Seed RNG per-request for reproducible simulation
    seeded_rng = random.Random(request_id)
    
    # Process pending conversation steps (seeded simulation).
    confirmed_count = 0
    for alert in alerts:
        if alert.get("reply") is not None or alert.get("stage", "awaiting_recency") == "done":
            if alert.get("reply") == "confirmed":
                confirmed_count += 1
            continue

        donor = db.get_donor(alert["donor_id"])
        score = 0.5
        reply = alerting.determine_reply(donor, score, seeded_rng)
        stage = alert.get("stage", "awaiting_recency")

        if stage == "awaiting_recency":
            if reply == "confirmed":
                # Simulation's positive propensity means the donor is not recent.
                db.update_alert_stage(alert["id"], "awaiting_confirm")
            elif reply == "declined":
                db.insert_donation(
                    donor_id=donor["id"],
                    donated_on=date.today().isoformat(),
                    units=1,
                    source="self_report",
                )
                db.update_alert_reply(alert["id"], "donated_recently", stage="done")
        elif stage == "awaiting_confirm":
            if reply in ("confirmed", "declined"):
                db.update_alert_reply(alert["id"], reply, stage="done")
                if reply == "confirmed":
                    receiver_details = _receiver_details_message(donor, req)
                    db.insert_audit_log(
                        actor="simulator",
                        action="receiver_details_message",
                        entity="alert",
                        entity_id=alert["id"],
                        detail=receiver_details
                    )
                    confirmed_count += 1
    
    # Check if fulfilled
    if confirmed_count >= req.get("units", 1):
        # Request is fulfilled!
        db.update_request_status(request_id, "fulfilled")
        db.insert_audit_log(
            actor="simulator",
            action="fulfill_request",
            entity="request",
            entity_id=request_id,
            detail=f"Fulfilled with {confirmed_count} confirmed donors"
        )
        flash(f"Request fulfilled! {confirmed_count} donors confirmed.", "success")
    else:
        # Not enough confirmations, fire Wave 2
        all_donors = db.get_donors_by_city(req["city"])
        
        rules_list = db.get_all_rules()
        rules_dict = {r["key"]: r["value"] for r in rules_list}
        
        today = date.today()
        eligible_donors = []
        donations_by_donor = {}
        alerts_by_donor = {}
        
        for donor in all_donors:
            if not compatibility.is_compatible(donor["blood_group"], req["blood_group"], req.get("component", "whole_blood")):
                continue
            
            donations = db.get_donations_for_donor(donor["id"])
            donations_by_donor[donor["id"]] = donations
            alerts = db.get_alerts_for_donor(donor["id"])
            alerts_by_donor[donor["id"]] = alerts
            
            assessment = eligibility.assess_donor(donor, donations, rules_dict, today)
            donor_info = dict(donor)
            donor_info["eligibility_status"] = assessment["status"]
            
            if assessment["status"] == "eligible":
                eligible_donors.append(donor_info)
        
        # Rank eligible donors
        ranked_with_scores = predictor.rank_donors(
            req,
            eligible_donors,
            donations_by_donor,
            alerts_by_donor,
            today
        )
        
        # Plan waves
        now = datetime.now()
        plan = alerting.plan_waves(ranked_with_scores, req, alerts_by_donor, now)
        
        # Write Wave 2 alerts (exclude donors already alerted in Wave 1)
        wave1_donor_ids = set(a["donor_id"] for a in wave1_alerts)
        wave2_donors = [d for d in plan["wave2"] if d["id"] not in wave1_donor_ids]
        
        # Get channel from Wave 1 (for Wave 2 alerts)
        wave1_channel = wave1_alerts[0].get("channel", "simulator") if wave1_alerts else "simulator"
        
        for donor in wave2_donors:
            db.insert_alert(
                request_id=request_id,
                donor_id=donor["id"],
                wave_no=2,
                channel=wave1_channel
            )
            
            # If WhatsApp channel, send message via bridge
            if wave1_channel == "whatsapp":
                _send_whatsapp_alert(donor, req)
        
        # Write audit log
        db.insert_audit_log(
            actor="simulator",
            action="fire_wave2",
            entity="request",
            entity_id=request_id,
            detail=f"Wave 1 had {confirmed_count}/{req.get('units', 1)} confirmations, firing Wave 2 with {len(wave2_donors)} donors on {wave1_channel}"
        )
        
        flash(f"Wave 1 had {confirmed_count} confirmations (needed {req.get('units', 1)}). Firing Wave 2 with {len(wave2_donors)} donors.", "info")
    
    return redirect(url_for("request_status", request_id=request_id, staff=1))

@app.route("/request/<int:request_id>/donor/<int:donor_id>/mark-donated", methods=["POST"])
def mark_donated(request_id, donor_id):
    """Mark a confirmed donor as having donated."""
    staff_check = require_staff()
    if staff_check:
        return staff_check
    
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    req = db.get_request(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("home"))
    
    donor = db.get_donor(donor_id)
    if not donor:
        flash("Donor not found.", "error")
        return redirect(url_for("request_status", request_id=request_id, staff=1))
    
    # Find the alert for this donor
    alerts = db.get_alerts_for_request(request_id)
    alert = next((a for a in alerts if a["donor_id"] == donor_id), None)
    
    if not alert:
        flash("No alert found for this donor.", "error")
        return redirect(url_for("request_status", request_id=request_id, staff=1))
    
    if alert.get("reply") != "confirmed":
        flash("Only confirmed donors can be marked as donated.", "error")
        return redirect(url_for("request_status", request_id=request_id, staff=1))
    
    # Write donations row
    db.insert_donation(
        donor_id=donor_id,
        donated_on=date.today(),
        units=1,
        request_id=request_id,
        source="simulator"
    )
    
    # Mark alert as showed_up
    db.update_alert_showup(alert["id"], True)
    
    # Write audit log
    db.insert_audit_log(
        actor="staff",
        action="mark_donated",
        entity="donor",
        entity_id=donor_id,
        detail=f"Marked as donated for request {request_id}"
    )
    
    flash(f"{donor['name']} marked as donated.", "success")
    return redirect(url_for("request_status", request_id=request_id, staff=1))

# === STAGE 1 MATCH PREVIEW ===

@app.route("/match/<int:request_id>")
def match_preview(request_id):
    """Stage 3 match preview: includes eligibility, compatibility, and predicted show-up probability."""
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    req = db.get_request(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("home"))

    # Get all donors in the same city
    all_donors = db.get_donors_by_city(req["city"])
    
    # Get rules for eligibility assessment
    rules_list = db.get_all_rules()
    rules_dict = {r["key"]: r["value"] for r in rules_list}
    
    # Assess and categorize donors
    today = datetime.now().date()
    eligible_donors = []
    deferred_donors = []
    
    # Build donation and alert history dicts for ranking
    donations_by_donor = {}
    alerts_by_donor = {}
    
    for donor in all_donors:
        # Check blood type compatibility
        if not compatibility.is_compatible(donor["blood_group"], req["blood_group"], req["component"]):
            continue
        
        # Get donor's donation history
        donations = db.get_donations_for_donor(donor["id"])
        donations_by_donor[donor["id"]] = donations
        
        # For Stage 3: get donor's alert history (can be empty)
        alerts = db.get_alerts_for_donor(donor["id"]) if hasattr(db, 'get_alerts_for_donor') else []
        alerts_by_donor[donor["id"]] = alerts
        
        # Assess eligibility
        assessment = eligibility.assess_donor(donor, donations, rules_dict, today)
        
        donor_info = dict(donor)
        donor_info["eligibility_status"] = assessment["status"]
        donor_info["eligible_on"] = assessment.get("eligible_on")
        donor_info["reasons"] = assessment.get("reasons", [])
        
        if assessment["status"] == "eligible":
            eligible_donors.append(donor_info)
        else:
            deferred_donors.append(donor_info)
    
    # Stage 3: Rank eligible donors by predicted show-up probability
    ranked_with_scores = predictor.rank_donors(
        req,
        eligible_donors,
        donations_by_donor,
        alerts_by_donor,
        today
    )
    
    # Convert to list of dicts with score and reason
    eligible_donors_ranked = []
    for donor, score, reason in ranked_with_scores:
        donor_with_score = dict(donor)
        donor_with_score["predicted_showup"] = score
        donor_with_score["prediction_reason"] = reason
        donor_with_score["exact_match"] = donor["blood_group"] == req["blood_group"]
        eligible_donors_ranked.append(donor_with_score)

    return render_template(
        "match_preview.html",
        request=req,
        eligible_donors=eligible_donors_ranked,
        deferred_donors=deferred_donors,
        stage="Stage 3 (AI-ranked)",
        synthetic_data=True
    )

# === STAFF ===

# === STAGE 5 STAFF DASHBOARD ===

@app.route("/staff")
def staff_dashboard():
    """Staff dashboard showing request queue grouped by status."""
    staff_check = require_staff()
    if staff_check:
        return staff_check
    
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))
    
    # Get requests grouped by status
    all_requests = db.get_all_requests()
    
    requests_by_status = {
        "pending_verification": [],
        "verified": [],
        "active": [],
        "fulfilled": [],
        "rejected": [],
    }
    
    for req in all_requests:
        status = req.get("status", "pending_verification")
        if status in requests_by_status:
            requests_by_status[status].append(req)
    
    return render_template(
        "staff_dashboard.html",
        requests_by_status=requests_by_status,
        is_staff=True
    )

@app.route("/staff/donors")
def staff_donor_directory():
    """Staff donor directory with eligibility badges."""
    staff_check = require_staff()
    if staff_check:
        return staff_check
    
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))
    
    # Get all donors and filter
    all_donors = db.get_all_donors()
    
    blood_group = request.args.get("blood_group", "")
    city = request.args.get("city", "")
    
    if blood_group:
        all_donors = [d for d in all_donors if d.get("blood_group") == blood_group]
    if city:
        all_donors = [d for d in all_donors if d.get("city") == city]
    
    # Assess eligibility for each donor
    rules_list = db.get_all_rules()
    rules_dict = {r["key"]: r["value"] for r in rules_list}
    today = date.today()
    
    donor_with_badges = []
    for donor in all_donors:
        donations = db.get_donations_for_donor(donor["id"])
        assessment = eligibility.assess_donor(donor, donations, rules_dict, today)
        donor_info = dict(donor)
        donor_info["eligibility_badge"] = f"{assessment['status'].title()}"
        if assessment.get("eligible_on"):
            donor_info["eligible_on"] = assessment["eligible_on"]
        donor_info["reasons"] = assessment.get("reasons", [])
        donor_with_badges.append(donor_info)
    
    return render_template(
        "staff_donors.html",
        donors=donor_with_badges,
        is_staff=True
    )

@app.route("/staff/experiment", methods=["GET", "POST"])
def experiment_mode():
    """Experiment mode: compare alerting strategies on synthetic donors."""
    staff_check = require_staff()
    if staff_check:
        return staff_check
    
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))
    
    if request.method == "GET":
        return render_template("experiment_mode.html", is_staff=True)
    
    # POST: run experiment
    try:
        pool_size = int(request.form.get("pool_size", 100))
        units_needed = int(request.form.get("units_needed", 2))
        trials = int(request.form.get("trials", 20))
        seed = int(request.form.get("seed", 42))
    except (ValueError, TypeError):
        flash("Invalid parameters.", "error")
        return redirect(url_for("experiment_mode", staff=1))
    
    import random as py_random
    py_random.seed(seed)
    
    results = {
        "broadcast": {"alerts_sent": [], "time_to_fulfill": [], "success_rate": []},
        "waves": {"alerts_sent": [], "time_to_fulfill": [], "success_rate": []},
    }
    
    # Run trials
    for trial in range(trials):
        # Generate synthetic donor pool
        synthetic_donors = []
        for _ in range(pool_size):
            synthetic_donors.append({
                "id": py_random.randint(10000, 99999),
                "name": f"Synthetic_{py_random.randint(1, 9999)}",
                "blood_group": py_random.choice(["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]),
                "predicted_score": py_random.random(),
            })
        
        # Simulate Broadcast (alert all at once)
        seeded_rng = py_random.Random(seed + trial)
        confirmations_broadcast = 0
        for donor in synthetic_donors:
            if alerting.determine_reply(donor, donor["predicted_score"], seeded_rng) == "confirmed":
                confirmations_broadcast += 1
            if confirmations_broadcast >= units_needed:
                break
        
        results["broadcast"]["alerts_sent"].append(len(synthetic_donors))
        results["broadcast"]["time_to_fulfill"].append(10)  # One wave window
        results["broadcast"]["success_rate"].append(1.0 if confirmations_broadcast >= units_needed else 0.0)
        
        # Simulate Waves (top 10, then next 20)
        sorted_donors = sorted(synthetic_donors, key=lambda d: d["predicted_score"], reverse=True)
        seeded_rng = py_random.Random(seed + trial)
        
        confirmations_wave1 = 0
        alerts_sent_w1 = min(10, len(sorted_donors))
        for donor in sorted_donors[:10]:
            if alerting.determine_reply(donor, donor["predicted_score"], seeded_rng) == "confirmed":
                confirmations_wave1 += 1
            if confirmations_wave1 >= units_needed:
                break
        
        time_wave = 10 if confirmations_wave1 >= units_needed else 20
        alerts_sent_total = alerts_sent_w1
        confirmations_total = confirmations_wave1
        
        if confirmations_wave1 < units_needed and len(sorted_donors) > 10:
            alerts_sent_w2 = min(20, len(sorted_donors) - 10)
            for donor in sorted_donors[10:30]:
                if alerting.determine_reply(donor, donor["predicted_score"], seeded_rng) == "confirmed":
                    confirmations_total += 1
                if confirmations_total >= units_needed:
                    break
            alerts_sent_total = alerts_sent_w1 + alerts_sent_w2
        
        results["waves"]["alerts_sent"].append(alerts_sent_total)
        results["waves"]["time_to_fulfill"].append(time_wave)
        results["waves"]["success_rate"].append(1.0 if confirmations_total >= units_needed else 0.0)
    
    # Calculate averages
    summary = {
        "broadcast": {
            "avg_alerts": sum(results["broadcast"]["alerts_sent"]) / max(len(results["broadcast"]["alerts_sent"]), 1),
            "avg_time": sum(results["broadcast"]["time_to_fulfill"]) / max(len(results["broadcast"]["time_to_fulfill"]), 1),
            "avg_success": sum(results["broadcast"]["success_rate"]) / max(len(results["broadcast"]["success_rate"]), 1),
        },
        "waves": {
            "avg_alerts": sum(results["waves"]["alerts_sent"]) / max(len(results["waves"]["alerts_sent"]), 1),
            "avg_time": sum(results["waves"]["time_to_fulfill"]) / max(len(results["waves"]["time_to_fulfill"]), 1),
            "avg_success": sum(results["waves"]["success_rate"]) / max(len(results["waves"]["success_rate"]), 1),
        },
    }
    
    return render_template(
        "experiment_results.html",
        summary=summary,
        pool_size=pool_size,
        units_needed=units_needed,
        trials=trials,
        seed=seed,
        is_staff=True
    )

# === STAGE 6: WHATSAPP INTEGRATION ===

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for deployment and bridge connectivity."""
    return {"ok": True}, 200

@app.route("/internal/ping", methods=["GET"])
def internal_ping():
    """Authenticated bridge startup check."""
    bridge_secret = os.getenv("BRIDGE_SECRET", "")
    if not bridge_secret or request.headers.get("X-Bridge-Secret", "") != bridge_secret:
        return ("", 401)
    return {"ok": True}, 200

@app.route("/internal/whatsapp-reply", methods=["POST"])
def whatsapp_reply():
    """Receive WhatsApp donor replies from the bridge.
    
    Expects:
    - X-Bridge-Secret header matching BRIDGE_SECRET env var
    - JSON body: {phone, text, message_id}
    
    Returns 401 if secret doesn't match.
    Returns 200 (idempotent) even if phone/message_id don't match any pending alert.
    """
    bridge_secret = os.getenv("BRIDGE_SECRET", "")
    request_secret = request.headers.get("X-Bridge-Secret", "")
    
    if not bridge_secret or request_secret != bridge_secret:
        return ("", 401)
    
    if not db.is_db_configured():
        return {"error": "Database not configured"}, 503
    
    try:
        data = request.get_json() or {}
        phone = data.get("phone", "").strip()
        text = data.get("text", "").strip()
        message_id = data.get("message_id", "")
        
        if not phone or not text or not message_id:
            return {"error": "Missing phone, text, or message_id"}, 400
        
        # Match inbound bridge numbers by digits only for legacy/live records.
        inbound_phone = "".join(character for character in phone if character.isdigit())
        donor = next(
            (
                candidate for candidate in db.get_all_donors()
                if "".join(
                    character for character in str(candidate.get("phone", ""))
                    if character.isdigit()
                ) == inbound_phone
            ),
            None,
        )
        if not donor:
            print(f"WhatsApp reply matched no donor for sender {phone!r}")
            return {"status": "no_donor_for_phone"}, 200
        
        # Get all alerts for this donor to check for duplicate message_id
        all_alerts = db.get_alerts_for_donor(donor["id"])
        
        # Check for duplicate message_id across all alerts (idempotent)
        for alert in all_alerts:
            if alert.get("message_id") == message_id:
                return {"status": "already_processed"}, 200
        
        # Find the donor's current conversation (one that is not done).
        matching_alert = None
        for alert in all_alerts:
            if alert.get("stage", "awaiting_recency") != "done" and alert.get("reply") is None:
                matching_alert = alert
                break
        
        if not matching_alert:
            # No pending alert; ignore (idempotent)
            print(f"WhatsApp reply matched no pending alert for sender {phone!r}")
            return {"status": "no_pending_alert"}, 200
        
        # Process the reply
        request_obj = db.get_request(matching_alert["request_id"])
        if not request_obj:
            return {"status": "request_not_found"}, 200
        
        stage = matching_alert.get("stage", "awaiting_recency")
        if stage == "awaiting_recency":
            if text == "1":
                db.update_alert_reply(
                    matching_alert["id"], "donated_recently",
                    message_id=message_id, stage="done"
                )
                db.update_alert_showup(matching_alert["id"], False)
                db.insert_donation(
                    donor_id=donor["id"],
                    donated_on=date.today().isoformat(),
                    units=1,
                    source="self_report"
                )
                _send_whatsapp_message(
                    phone,
                    "Thank you for letting us know. Please take care of yourself — "
                    "we will contact you when you are eligible again."
                )
                return {"status": "reply_recorded", "reply": "donated_recently"}, 200
            if text == "2":
                db.update_alert_stage(matching_alert["id"], "awaiting_confirm", message_id=message_id)
                _send_whatsapp_message(phone, _confirm_message(request_obj))
                return {"status": "awaiting_confirm"}, 200
            _send_whatsapp_message(
                phone,
                f"Please reply 1 = Yes, 2 = No. {_recency_message(request_obj)}"
            )
            return {"status": "invalid_reply_reask_sent", "stage": stage}, 200

        if stage == "awaiting_confirm":
            if text == "1":
                processed_reply = "confirmed"
            elif text == "2":
                processed_reply = "declined"
            else:
                _send_whatsapp_message(
                    phone,
                    "Please reply 1 = Yes, I can come, 2 = Not this time. "
                    f"{_confirm_message(request_obj)}"
                )
                return {"status": "invalid_reply_reask_sent", "stage": stage}, 200

            db.update_alert_reply(
                matching_alert["id"], processed_reply,
                message_id=message_id, stage="done"
            )
            db.update_alert_showup(matching_alert["id"], processed_reply == "confirmed")
            if processed_reply == "confirmed":
                receiver_details = _receiver_details_message(donor, request_obj)
                if matching_alert.get("channel") == "simulator":
                    db.insert_audit_log(
                        actor="simulator",
                        action="receiver_details_message",
                        entity="alert",
                        entity_id=matching_alert["id"],
                        detail=receiver_details
                    )
                elif not _send_whatsapp_message(donor["phone"], receiver_details):
                    db.insert_audit_log(
                        actor="whatsapp_system",
                        action="receiver_details_send_failed",
                        entity="alert",
                        entity_id=matching_alert["id"],
                        detail=receiver_details
                    )

        # Re-evaluate request: check if fulfilled
        confirmed_count = 0
        alerts_for_request = db.get_alerts_for_request(matching_alert["request_id"])
        for alert in alerts_for_request:
            if alert.get("reply") == "confirmed":
                confirmed_count += 1
        
        if confirmed_count >= request_obj.get("units", 1):
            db.update_request_status(matching_alert["request_id"], "fulfilled")
            db.insert_audit_log(
                actor="whatsapp_donor",
                action="request_fulfilled",
                entity="request",
                entity_id=matching_alert["request_id"],
                detail=f"Fulfilled via WhatsApp after {confirmed_count} confirmations"
            )
            return {"status": "request_fulfilled"}, 200
        
        # Wave not exhausted, proceed with next wave if still needed
        # (Fire Wave 2 if Wave 1 exhausted but not fulfilled)
        wave1_alerts = [a for a in alerts_for_request if a["wave_no"] == 1]
        wave2_alerts = [a for a in alerts_for_request if a["wave_no"] == 2]
        
        if len(wave2_alerts) == 0 and confirmed_count < request_obj.get("units", 1):
            # Wave 1 exhausted, units still needed: fire Wave 2 via WhatsApp
            # (This mirrors the simulator advance_simulation logic)
            # For now, just log it; Wave 2 firing happens in advance_simulation or separate logic
            pass
        
        return {"status": "reply_recorded", "reply": processed_reply}, 200
    
    except Exception as e:
        print(f"WhatsApp reply processing error: {e}")
        return {"error": str(e)}, 500

# === ERROR HANDLERS ===

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
