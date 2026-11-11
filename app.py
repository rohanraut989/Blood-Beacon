"""
BloodBeacon — Emergency Blood-Donor Activation System
Flask application
"""

import os
import random
import requests
from datetime import datetime, date, timedelta
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
CASCADE_WINDOW_MINUTES = 2

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
                _reevaluate_open_requests_for_donor(donor)
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

            try:
                needed_dt = datetime.fromisoformat(needed_by.replace("Z", "+00:00"))
            except ValueError:
                flash("Needed By must be a valid date and time.", "error")
                return redirect(url_for("request_blood"))
            current_time = datetime.now(needed_dt.tzinfo) if needed_dt.tzinfo else datetime.now()
            if needed_dt <= current_time:
                flash("Needed By must be in the future.", "error")
                return redirect(url_for("request_blood"))
            normalized_contact = "".join(character for character in contact_phone if character.isdigit())
            now = datetime.now()
            recent_requests = db.get_all_requests()
            contact_requests = [
                candidate for candidate in recent_requests
                if "".join(character for character in str(candidate.get("contact_phone", "")) if character.isdigit())
                == normalized_contact
            ]
            if any(candidate.get("status") == "active" for candidate in contact_requests):
                flash("This contact already has an active request.", "error")
                return redirect(url_for("request_blood"))
            recent_cutoff = now.timestamp() - 24 * 60 * 60
            recent_count = 0
            for candidate in contact_requests:
                try:
                    created = datetime.fromisoformat(str(candidate.get("created_at", "")).replace("Z", "+00:00"))
                    if created.timestamp() >= recent_cutoff:
                        recent_count += 1
                except ValueError:
                    continue
            if recent_count >= 3:
                flash("This contact has reached the 24-hour request limit.", "error")
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
                db.verify_request(req["id"], "system (auto)")
                db.insert_audit_log(
                    actor="system",
                    action="verify_request",
                    entity="request",
                    entity_id=req["id"],
                    detail="Automatically verified on public submission"
                )
                activate_request(req["id"], _internal=True)
                if db.get_alerts_for_request(req["id"]):
                    message = (
                        f"Request submitted for {patient_name}. "
                        f"Status: Active — donors are being alerted (id: {req['id']})"
                    )
                else:
                    message = (
                        f"Request submitted for {patient_name}. "
                        "No matching donors are available yet; the request remains open."
                    )
                flash(message, "success")
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

def _maybe_auto_advance(request_id):
    _evaluate_cascade(request_id)


def _cascade_window_minutes():
    rule = db.get_rule("CASCADE_WINDOW_MINUTES")
    if rule and rule.get("value") is not None:
        try:
            return max(float(rule["value"]), 0)
        except (TypeError, ValueError):
            pass
    return CASCADE_WINDOW_MINUTES


def _alert_sent_datetime(alert):
    value = alert.get("sent_at") or alert.get("created_at")
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _cascade_send_alert(req, donor, channel, wave_no=1):
    alert = db.insert_alert(
        request_id=req["id"],
        donor_id=donor["id"],
        wave_no=wave_no,
        channel=channel,
        match_tier=donor.get("match_tier", 1),
        cross_group=donor.get("cross_group", False),
    )
    if channel == "whatsapp":
        _send_whatsapp_alert(donor, req)
    return alert


def _stand_down_active_alerts(req, alerts):
    for alert in alerts:
        if alert.get("stage") == "done" or alert.get("reply") is not None:
            continue
        donor = db.get_donor(alert["donor_id"])
        db.update_alert_reply(alert["id"], "covered", stage="done")
        if donor:
            message = (
                f"Good news, {_donor_first_name(donor)} — this request just got covered "
                "by another donor. Thank you for being ready to help. 🙏"
            )
            if alert.get("channel") == "simulator":
                db.insert_audit_log("simulator", "stand_down_sent", "alert", alert["id"], message)
            else:
                _send_whatsapp_message(donor["phone"], message)
        db.insert_audit_log(
            actor="system",
            action="stand_down_sent",
            entity="alert",
            entity_id=alert["id"],
            detail=f"Request {req['id']} was fulfilled",
        )


def _evaluate_cascade(request_id, channel=None):
    """Sweep expired asks, refill free unit slots, and settle fulfilment."""
    req = db.get_request(request_id)
    if not req or req.get("status") != "active":
        return
    now = datetime.now()
    alerts = db.get_alerts_for_request(request_id)
    window = _cascade_window_minutes()

    for alert in alerts:
        if alert.get("stage") == "done" or alert.get("reply") is not None:
            continue
        sent_at = _alert_sent_datetime(alert)
        if sent_at and (now - sent_at).total_seconds() >= window * 60:
            db.update_alert_reply(alert["id"], "passed", stage="done")
            db.insert_audit_log(
                actor="system",
                action="cascade_passed",
                entity="alert",
                entity_id=alert["id"],
                detail=f"Reply window expired after {window:g} minutes",
            )

    confirmed = _confirmed_count(request_id)
    units = int(float(req.get("units", 0) or 0))
    if confirmed >= units:
        db.update_request_status(request_id, "fulfilled")
        _stand_down_active_alerts(req, db.get_alerts_for_request(request_id))
        channel = next(
            (alert.get("channel") for alert in db.get_alerts_for_request(request_id)
             if alert.get("channel")),
            "whatsapp",
        )
        _notify_receiver_fulfillment(req, channel=channel)
        db.insert_audit_log(
            actor="system",
            action="request_fulfilled",
            entity="request",
            entity_id=request_id,
            detail=f"Cascade fulfilled with {confirmed} confirmations",
        )
        return

    alerts = db.get_alerts_for_request(request_id)
    active_count = sum(
        1 for alert in alerts
        if alert.get("stage") != "done" and alert.get("reply") is None
    )
    slots = max(units - confirmed - active_count, 0)
    if not slots:
        return

    ranked, alerts_by_donor, _ = _ranked_match_pool(req)
    asked_ids = {alert["donor_id"] for alert in alerts}
    channel = channel or next(
        (alert.get("channel") for alert in alerts if alert.get("channel")),
        "whatsapp",
    )
    for donor, score, reason in ranked:
        if slots <= 0:
            break
        if donor["id"] in asked_ids:
            continue
        plan = alerting.plan_waves(
            [(donor, score, reason)], req, alerts_by_donor, now
        )
        if not plan["wave1"]:
            continue
        _cascade_send_alert(req, donor, channel)
        asked_ids.add(donor["id"])
        slots -= 1
        db.insert_audit_log(
            actor="system",
            action="cascade_advanced",
            entity="request",
            entity_id=request_id,
            detail=f"Asked donor {donor.get('name', donor['id'])}",
        )


def _reevaluate_open_requests_for_donor(donor):
    """Refill active requests when a newly registered donor becomes eligible."""
    for req in db.get_all_requests():
        if req.get("status") != "active":
            continue
        if not compatibility.is_compatible(
            donor.get("blood_group"),
            req.get("blood_group"),
            req.get("component", "whole_blood"),
        ):
            continue
        before = len(db.get_alerts_for_request(req["id"]))
        _evaluate_cascade(req["id"])
        after = len(db.get_alerts_for_request(req["id"]))
        if after > before:
            db.insert_audit_log(
                actor="system",
                action="cascade_advanced",
                entity="request",
                entity_id=req["id"],
                detail=f"New donor {donor.get('id')} registered; cascade reevaluated",
            )


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

    _maybe_auto_advance(request_id)
    req = db.get_request(request_id)
    staff_mode = False
    
    # Get alerts for this request (if any)
    alerts = db.get_alerts_for_request(request_id)
    
    # Build alert details with donor info
    alert_details = []
    for alert in alerts:
        donor = db.get_donor(alert["donor_id"])
        alert_with_donor = dict(alert)
        alert_with_donor["donor"] = donor
        alert_details.append(alert_with_donor)

    return render_template(
        "request_status.html",
        request=req,
        is_staff=False,
        alerts=alert_details,
        tier_counts={
            "exact": sum(1 for alert in alerts if alert.get("wave_no") == 1 and alert.get("match_tier", 1) == 1),
            "compatible": sum(1 for alert in alerts if alert.get("wave_no") == 1 and alert.get("match_tier") == 2),
            "far": sum(1 for alert in alerts if alert.get("wave_no") == 1 and alert.get("match_tier") == 3),
        },
        confirmed_donors=[
            alert["donor"] for alert in alert_details
            if alert.get("reply") == "confirmed" and alert.get("donor")
        ],
    )


def _confirmation_status(request_obj):
    """Return the receiver-safe, confirmation-ordered donor state."""
    confirmed = []
    for alert in db.get_alerts_for_request(request_obj["id"]):
        if alert.get("reply") != "confirmed":
            continue
        donor = db.get_donor(alert["donor_id"])
        if donor:
            confirmed.append({
                "donor_name": donor.get("name", ""),
                "blood_group": donor.get("blood_group", ""),
                "donor_phone": donor.get("phone", ""),
                "_order": alert.get("replied_at") or alert.get("created_at") or "",
                "_alert_id": alert.get("id", 0),
            })
    confirmed.sort(key=lambda donor: (donor["_order"], donor["_alert_id"]))
    for donor in confirmed:
        donor.pop("_order", None)
        donor.pop("_alert_id", None)
    return {
        "status": request_obj.get("status"),
        "units_needed": int(float(request_obj.get("units", 0) or 0)),
        "confirmed_count": len(confirmed),
        "confirmed": confirmed,
    }


@app.route("/request/<int:request_id>/status.json")
def request_status_json(request_id):
    request_obj = db.get_request(request_id)
    if not request_obj:
        return jsonify({"error": "Request not found"}), 404
    _maybe_auto_advance(request_id)
    request_obj = db.get_request(request_id)
    return jsonify(_confirmation_status(request_obj))

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
    req = db.get_request(request_id)
    if not session.get("staff_console") or not req:
        return ("Staff access required.", 403)
    if req["status"] not in ["active", "verified"]:
        return redirect(url_for("request_status", request_id=request_id))
    db.cancel_alerts_for_request(request_id)
    db.close_request(request_id, "staff", "Closed by staff console")
    return redirect(url_for("staff_dashboard"))

@app.route("/request/<int:request_id>/close-public", methods=["POST"])
def close_public_request(request_id):
    req = db.get_request(request_id)
    if not req or req.get("status") not in ("active", "verified"):
        return redirect(url_for("request_status", request_id=request_id))
    db.cancel_alerts_for_request(request_id)
    db.close_request(request_id, "receiver", "Closed by receiver")
    return redirect(url_for("request_status", request_id=request_id))

@app.route("/request/<int:request_id>/fulfill", methods=["POST"])
def fulfill_public_request(request_id):
    req = db.get_request(request_id)
    if not req or req.get("status") != "active":
        return redirect(url_for("request_status", request_id=request_id))
    db.update_request_status(request_id, "fulfilled")
    _notify_receiver_fulfillment(req)
    db.insert_audit_log(
        actor="receiver",
        action="fulfill_request",
        entity="request",
        entity_id=request_id,
        detail="Marked fulfilled by receiver",
    )
    return redirect(url_for("request_status", request_id=request_id))

@app.route("/request/<int:request_id>/activate", methods=["POST"])
def activate_request(request_id, _internal=False):
    """Activate a request and send Wave 1 alerts."""
    if not _internal:
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
    
    # Activate request
    _, _, eligible_pool_count = _ranked_match_pool(req)
    db.update_request_match_pool_count(
        request_id,
        eligible_pool_count
    )
    db.update_request_status(request_id, "active")
    
    # Determine channel (whatsapp for real requests, simulator for testing)
    channel = request.args.get("channel", "whatsapp")  # Default to whatsapp
    _evaluate_cascade(request_id, channel=channel)
    db.insert_audit_log(
        actor="staff_simulator",
        action="activate_request",
        entity="request",
        entity_id=request_id,
        detail=f"Sequential cascade activated on {channel}"
    )
    
    active_asks = sum(
        1 for alert in db.get_alerts_for_request(request_id)
        if alert.get("stage") != "done" and alert.get("reply") is None
    )
    flash(f"Request activated! {active_asks} donor(s) asked.", "success")
    return redirect(url_for("request_status", request_id=request_id, staff=1))


def _ranked_match_pool(req):
    """Build the tiered, currently eligible pool in deterministic tier order."""
    rules_list = db.get_all_rules()
    rules_dict = {rule["key"]: rule["value"] for rule in rules_list}
    today = date.today()
    eligible_by_tier = {1: [], 2: [], 3: []}
    donations_by_donor = {}
    alerts_by_donor = {}
    exclusions = []

    for donor in db.get_all_donors():
        donor_id = donor.get("id", "?")
        try:
            if not compatibility.is_compatible(
                donor["blood_group"], req["blood_group"], req.get("component", "whole_blood")
            ):
                exclusions.append((donor_id, "incompatible blood group"))
                continue
        except (KeyError, ValueError, TypeError) as error:
            exclusions.append((donor_id, f"compatibility error: {error}"))
            continue
        try:
            donations = db.get_donations_for_donor(donor_id) or []
            donations_by_donor[donor_id] = donations
            alerts = db.get_alerts_for_donor(donor_id) or []
            alerts_by_donor[donor_id] = alerts
            assessment = eligibility.assess_donor(donor, donations, rules_dict, today)
        except Exception as error:
            exclusions.append((donor_id, f"eligibility/history error: {error}"))
            continue
        if assessment["status"] != "eligible":
            exclusions.append((
                donor_id,
                "; ".join(assessment.get("reasons") or ["deferred"]),
            ))
            continue
        donor_info = dict(donor)
        donor_info["eligibility_status"] = assessment["status"]
        exact = donor.get("blood_group") == req.get("blood_group")
        same_city = donor.get("city") == req.get("city")
        donor_info["match_tier"] = 1 if same_city and exact else 2 if same_city else 3
        donor_info["cross_group"] = not exact
        eligible_by_tier[donor_info["match_tier"]].append(donor_info)

    ranked = []
    for tier in (1, 2, 3):
        try:
            ranked.extend(predictor.rank_donors(
                req, eligible_by_tier[tier], donations_by_donor,
                alerts_by_donor, today
            ))
        except Exception as error:
            # Keep pool construction fail-open if a legacy model or one
            # malformed history row breaks the batch rank operation.
            print(f"Predictor batch fallback for tier {tier}: {type(error).__name__}: {error}")
            ranked.extend((donor, 0.5, "neutral history") for donor in eligible_by_tier[tier])
    if exclusions:
        print(
            f"Match pool request {req.get('id')}: "
            + ", ".join(f"donor {donor_id}: {reason}" for donor_id, reason in exclusions)
        )
    pool_size = sum(len(donors) for donors in eligible_by_tier.values())
    print(
        f"Match pool request {req.get('id')}: eligible={pool_size}, "
        f"ranked={len(ranked)}, exclusions={len(exclusions)}"
    )
    return ranked, alerts_by_donor, pool_size


def _confirmed_count(request_id):
    return sum(
        1 for alert in db.get_alerts_for_request(request_id)
        if alert.get("reply") == "confirmed"
    )


def _patient_first_name(req):
    """Return only the patient's first name for donor-facing messages."""
    return (req.get("patient_name") or "A patient").split()[0]

def _recency_message(req):
    return (
        f"{_patient_first_name(req)} needs {req.get('blood_group')} blood at "
        f"{req.get('hospital_name')}, {req.get('city')}. "
        "Did you donate blood in the last 3 months? Reply 1 = Yes, 2 = No"
    )

def _cross_group_recency_message(donor, req):
    return (
        f"Urgent: {_patient_first_name(req)} needs {req.get('blood_group')} blood at "
        f"{req.get('hospital_name')}, {req.get('city')}. No {req.get('blood_group')} "
        f"donor was found nearby — but your {donor.get('blood_group')} blood can "
        "also be given to this patient. Did you donate blood in the last 3 months? "
        "Reply 1 = Yes, 2 = No"
    )

def _confirm_message(req):
    return (
        f"You can save a life today. Can you come to {req.get('hospital_name')} "
        f"to donate? Reply 1 = Yes, I can come, 2 = Not this time"
    )

DECLINED_CLOSE_TEMPLATE = (
    "No problem at all, {first_name} — thank you for responding. 🙏 "
    "You may save a life another day."
)
DONATED_RECENTLY_CLOSE_TEMPLATE = (
    "Thank you for donating, {first_name}! 🙏 We've noted this donation — "
    "you'll be eligible to donate again from {eligible_date}. Until then, rest well."
)
CONFIRMED_CLOSE_TEMPLATE = (
    "You're confirmed — thank you for stepping up, {first_name}! 🙏\n"
    "You're confirmed to donate "
)
LATE_REPLY_CLOSE_TEMPLATE = (
    "Thank you, {first_name} — this request has already been completed. 🙏"
)

def _donor_first_name(donor):
    return (donor.get("name") or "Donor").split()[0]

def _receiver_details_message(donor, req):
    return (
        f"{CONFIRMED_CLOSE_TEMPLATE.format(first_name=_donor_first_name(donor))}"
        f"{req.get('blood_group')} blood for {req.get('patient_name')} at "
        f"{req.get('hospital_name')}, {req.get('city')}. Receiver contact: "
        f"{req.get('patient_name')} — {req.get('contact_phone')}. Please call them "
        f"to coordinate. Needed by: {format_human_date(req.get('needed_by'))}."
    )

def _donated_recently_close_message(donor):
    gap_days = 120 if donor.get("gender") == "Female" else 90
    eligible_date = date.today() + timedelta(days=gap_days)
    return DONATED_RECENTLY_CLOSE_TEMPLATE.format(
        first_name=_donor_first_name(donor),
        eligible_date=f"{eligible_date.day} {eligible_date.strftime('%b %Y')}",
    )

def _conversation_close_message(donor, req, alert, outcome):
    first_name = _donor_first_name(donor)
    if outcome == "declined":
        return DECLINED_CLOSE_TEMPLATE.format(first_name=first_name)
    if outcome == "donated_recently":
        return _donated_recently_close_message(donor)
    if outcome == "confirmed":
        return _receiver_details_message(donor, req)
    if outcome == "late":
        return LATE_REPLY_CLOSE_TEMPLATE.format(first_name=first_name)
    raise ValueError(f"Unsupported conversation close outcome: {outcome}")

def _send_conversation_close(donor, req, alert, outcome):
    """Send or record one terminal conversation close, best effort."""
    if alert.get("close_sent"):
        return True
    message = _conversation_close_message(donor, req, alert, outcome)
    # Claim the close before sending so replayed events cannot send twice.
    db.update_alert_close_sent(alert["id"])
    if alert.get("channel") == "simulator":
        db.insert_audit_log(
            actor="simulator",
            action="receiver_details_message" if outcome == "confirmed" else "conversation_close_sent",
            entity="alert",
            entity_id=alert["id"],
            detail=message,
        )
        return True
    if _send_whatsapp_message(donor["phone"], message):
        return True
    db.insert_audit_log(
        actor="whatsapp_system",
        action=(
            "receiver_details_send_failed"
            if outcome == "confirmed"
            else "conversation_close_send_failed"
        ),
        entity="alert",
        entity_id=alert["id"],
        detail=message,
    )
    return False


def _receiver_confirmation_message(donor, req):
    status_page_url = url_for("request_status", request_id=req["id"], _external=True)
    return (
        f"Good news! {donor.get('name', 'A donor')} ({donor.get('blood_group')}) "
        f"has accepted your request and confirmed to donate for {req.get('patient_name')} "
        f"at {req.get('hospital_name')}, {req.get('city')}. Donor's number: "
        f"{donor.get('phone')}. You can contact the donor directly now. Track your "
        f"request: {status_page_url} — BloodBeacon"
    )


def _notify_receiver_confirmation(donor, req, alert):
    """Best-effort, exactly-once receiver notification for one confirmation."""
    if alert.get("receiver_notified"):
        return
    message = _receiver_confirmation_message(donor, req)
    try:
        sent = (
            db.insert_audit_log(
                actor="simulator",
                action="receiver_notified",
                entity="alert",
                entity_id=alert["id"],
                detail=message,
            )
            if alert.get("channel") == "simulator"
            else _send_whatsapp_message(req.get("contact_phone"), message)
        )
        if alert.get("channel") != "simulator" and not sent:
            db.insert_audit_log(
                actor="whatsapp_system",
                action="receiver_notify_failed",
                entity="alert",
                entity_id=alert["id"],
                detail=message,
            )
            return
        try:
            db.update_alert_receiver_notified(alert["id"])
        except Exception as error:
            print(f"Receiver notification flag update failed for alert {alert['id']}: {error}")
    except Exception as error:
        db.insert_audit_log(
            actor="whatsapp_system",
            action="receiver_notify_failed",
            entity="alert",
            entity_id=alert["id"],
            detail=f"{message} ({error})",
        )


def _fulfillment_message(req):
    units = format_unit_int(req.get("units"))
    return (
        f"All {units} unit(s) for {req.get('patient_name')} are now confirmed — "
        "your BloodBeacon request is fulfilled. Wishing a speedy recovery. 🙏"
    )


def _notify_receiver_fulfillment(req, channel="whatsapp", source_alert=None):
    """Best-effort, exactly-once fulfilment notification for a request."""
    if req.get("fulfilled_notified"):
        return
    message = _fulfillment_message(req)
    try:
        if channel == "simulator":
            db.insert_audit_log(
                actor="simulator",
                action="fulfilled_notified",
                entity="request",
                entity_id=req["id"],
                detail=message,
            )
        elif not _send_whatsapp_message(req.get("contact_phone"), message):
            db.insert_audit_log(
                actor="whatsapp_system",
                action="receiver_notify_failed",
                entity="request",
                entity_id=req["id"],
                detail=message,
            )
            return
        try:
            db.update_request_fulfilled_notified(req["id"])
        except Exception as error:
            print(f"Fulfilment notification flag update failed for request {req['id']}: {error}")
    except Exception as error:
        db.insert_audit_log(
            actor="whatsapp_system",
            action="receiver_notify_failed",
            entity="request",
            entity_id=req["id"],
            detail=f"{message} ({error})",
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
    message = (
        _cross_group_recency_message(donor, req)
        if donor.get("cross_group")
        else _recency_message(req)
    )
    _send_whatsapp_message(donor["phone"], message)

_WHATSAPP_VERIFY_PROMPT = (
    "To verify your WhatsApp, please reply with your registered mobile number."
)

# === STAGE 4 SIMULATOR ===

def _advance_cascade_simulation(request_id):
    req = db.get_request(request_id)
    if not req or req.get("status") != "active":
        return
    _evaluate_cascade(request_id, channel="simulator")
    seeded_rng = random.Random(request_id)
    for alert in list(db.get_alerts_for_request(request_id)):
        if alert.get("stage") == "done" or alert.get("reply") is not None:
            continue
        donor = db.get_donor(alert["donor_id"])
        reply = alerting.determine_reply(donor, 0.5, seeded_rng)
        if reply == "no_reply":
            continue
        if alert.get("stage") == "awaiting_recency":
            if reply == "declined":
                db.update_alert_reply(alert["id"], "donated_recently", stage="done")
                db.insert_donation(
                    donor_id=donor["id"], donated_on=date.today().isoformat(),
                    units=1, source="self_report",
                )
                _send_conversation_close(donor, req, alert, "donated_recently")
            else:
                db.update_alert_stage(alert["id"], "awaiting_confirm")
        else:
            outcome = "confirmed" if reply == "confirmed" else "declined"
            db.update_alert_reply(alert["id"], outcome, stage="done")
            _send_conversation_close(donor, req, alert, outcome)
            if outcome == "confirmed":
                _notify_receiver_confirmation(donor, req, alert)
    _evaluate_cascade(request_id, channel="simulator")

@app.route("/request/<int:request_id>/advance", methods=["POST"])
def advance_simulation(request_id, _internal=False):
    """Advance the simulator: process pending replies and fire Wave 2 if needed."""
    if not _internal:
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
    _advance_cascade_simulation(request_id)
    return redirect(url_for("request_status", request_id=request_id, staff=1))
    
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
                _send_conversation_close(donor, req, alert, "donated_recently")
        elif stage == "awaiting_confirm":
            if reply in ("confirmed", "declined"):
                db.update_alert_reply(alert["id"], reply, stage="done")
                if reply == "confirmed":
                    _send_conversation_close(donor, req, alert, "confirmed")
                    confirmed_count += 1
                else:
                    _send_conversation_close(donor, req, alert, "declined")
    
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
        all_donors = db.get_all_donors()
        
        rules_list = db.get_all_rules()
        rules_dict = {r["key"]: r["value"] for r in rules_list}
        
        today = date.today()
        eligible_by_tier = {1: [], 2: [], 3: []}
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
                exact = donor.get("blood_group") == req.get("blood_group")
                same_city = donor.get("city") == req.get("city")
                tier = 1 if same_city and exact else 2 if same_city else 3
                donor_info["match_tier"] = tier
                donor_info["cross_group"] = not exact
                eligible_by_tier[tier].append(donor_info)
        
        # Rank eligible donors
        ranked_with_scores = []
        for tier in (1, 2, 3):
            ranked_with_scores.extend(predictor.rank_donors(
                req, eligible_by_tier[tier], donations_by_donor,
                alerts_by_donor, today
            ))
        
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
                channel=wave1_channel,
                match_tier=donor.get("match_tier", 1),
                cross_group=donor.get("cross_group", False),
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
    
    return redirect(url_for("request_status", request_id=request_id))

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
    """Standalone demo-grade staff console."""
    if not session.get("staff_console"):
        return render_template("staff_console.html", authenticated=False)
    all_requests = db.get_all_requests()
    for req in all_requests:
        if req.get("status") == "active":
            _evaluate_cascade(req["id"])
    all_requests = db.get_all_requests()
    
    requests_by_status = {
        "pending_verification": [],
        "verified": [],
        "active": [],
        "fulfilled": [],
        "rejected": [],
        "closed": [],
    }
    
    for req in all_requests:
        status = req.get("status", "pending_verification")
        req["confirmed_donors"] = [
            db.get_donor(alert["donor_id"])
            for alert in db.get_alerts_for_request(req["id"])
            if alert.get("reply") == "confirmed"
        ]
        req["wave_outcomes"] = [
            entry for entry in db.get_audit_logs_for_entity("request", req["id"])
            if entry.get("action") in ("activate_request", "fire_wave2")
        ]
        if status in requests_by_status:
            requests_by_status[status].append(req)
    
    return render_template(
        "staff_console.html",
        requests_by_status=requests_by_status,
        donors=db.get_all_donors(),
        audit_logs=db.get_recent_audit_logs(),
        authenticated=True,
    )

@app.route("/staff/login", methods=["POST"])
def staff_login():
    expected = os.environ.get("STAFF_PASSCODE")
    if not expected or request.form.get("passcode") != expected:
        return render_template("staff_console.html", authenticated=False), 403
    session["staff_console"] = True
    return redirect(url_for("staff_dashboard"))

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
            if phone.endswith("@lid"):
                typed_digits = "".join(character for character in text if character.isdigit())
                donors = db.get_all_donors()
                exact = [
                    candidate for candidate in donors
                    if "".join(character for character in str(candidate.get("phone", ""))
                               if character.isdigit()) == typed_digits
                ]
                matches = exact
                if not exact and len(typed_digits) >= 10:
                    matches = [
                        candidate for candidate in donors
                        if "".join(character for character in str(candidate.get("phone", ""))
                                   if character.isdigit()).endswith(typed_digits)
                    ]
                if len(matches) == 1:
                    return {
                        "status": "pair_donor",
                        "pair_phone": "".join(
                            character for character in str(matches[0]["phone"])
                            if character.isdigit()
                        ),
                        "message": "WhatsApp verified. You can now reply 1 or 2 to donor alerts.",
                    }, 200
                if len(matches) > 1:
                    return {
                        "status": "pair_ambiguous",
                        "message": (
                            "We found more than one donor with that number. Please reply "
                            "again including your country code (91 for India, 977 for Nepal)."
                        ),
                    }, 200
                return {"status": "pair_no_match", "message": _WHATSAPP_VERIFY_PROMPT}, 200
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
            # A passed donor may resume while the request is still open.
            for alert in all_alerts:
                request_for_alert = db.get_request(alert["request_id"])
                if alert.get("reply") == "passed" and request_for_alert:
                    if request_for_alert.get("status") in ("fulfilled", "closed"):
                        _send_conversation_close(donor, request_for_alert, alert, "late")
                        return {"status": "late_reply_closed"}, 200
                    if request_for_alert.get("status") == "active":
                        db.update_alert_stage(alert["id"], "awaiting_recency")
                        alert["stage"] = "awaiting_recency"
                        alert["reply"] = None
                        db.insert_audit_log(
                            actor="system",
                            action="donor_resumed",
                            entity="alert",
                            entity_id=alert["id"],
                            detail=f"Late reply resumed donor {donor['id']}",
                        )
                        matching_alert = alert
                        break
            if matching_alert:
                pass
            else:
                # A late reply to a terminal request still receives one close.
                for alert in all_alerts:
                    terminal_request = db.get_request(alert["request_id"])
                    if (
                        terminal_request
                        and terminal_request.get("status") in ("fulfilled", "closed")
                        and not alert.get("close_sent")
                    ):
                        _send_conversation_close(donor, terminal_request, alert, "late")
                        return {"status": "late_reply_closed"}, 200
                # No pending alert; ignore (idempotent)
                print(f"WhatsApp reply matched no pending alert for sender {phone!r}")
                return {"status": "no_pending_alert"}, 200
        
        # Process the reply
        request_obj = db.get_request(matching_alert["request_id"])
        if not request_obj:
            return {"status": "request_not_found"}, 200
        if request_obj.get("status") in ("closed", "fulfilled"):
            matching_alert["stage"] = "done"
            _send_conversation_close(donor, request_obj, matching_alert, "late")
            db.insert_audit_log(
                actor="whatsapp_donor",
                action="reply_to_closed_request",
                entity="request",
                entity_id=request_obj["id"],
                detail=f"Ignored reply from {phone!r}",
            )
            return {"status": "request_closed"}, 200
        
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
                _send_conversation_close(
                    donor, request_obj, matching_alert, "donated_recently"
                )
                _evaluate_cascade(request_obj["id"])
                return {"status": "reply_recorded", "reply": "donated_recently"}, 200
            if text == "2":
                db.update_alert_stage(matching_alert["id"], "awaiting_confirm", message_id=message_id)
                _send_whatsapp_message(phone, _confirm_message(request_obj))
                _evaluate_cascade(request_obj["id"])
                return {"status": "awaiting_confirm"}, 200
            _send_whatsapp_message(
                phone,
                f"Please reply 1 = Yes, 2 = No. "
                f"{_cross_group_recency_message(donor, request_obj) if matching_alert.get('cross_group') else _recency_message(request_obj)}"
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
                _send_conversation_close(
                    donor, request_obj, matching_alert, "confirmed"
                )
                _notify_receiver_confirmation(donor, request_obj, matching_alert)
            elif processed_reply == "declined":
                _send_conversation_close(
                    donor, request_obj, matching_alert, "declined"
                )
        _evaluate_cascade(request_obj["id"])
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
