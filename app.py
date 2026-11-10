"""
BloodBeacon — Emergency Blood-Donor Activation System
Flask application
"""

import os
import random
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import db
import eligibility
import compatibility
import predictor
import alerting

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

PORT = int(os.getenv("PORT", 5001))

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
            phone = request.form.get("phone", "").strip()
            gender = request.form.get("gender", "").strip()
            date_of_birth = request.form.get("date_of_birth", "").strip()
            weight_kg = float(request.form.get("weight_kg", 0))

            # Validate required fields
            if not all([name, blood_group, city, phone, gender, date_of_birth, weight_kg]):
                flash("All fields are required.", "error")
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

    # Check if staff mode is enabled
    is_staff = request.args.get("staff") == "1"
    
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
        is_staff=is_staff,
        alerts=alert_details
    )

# === STAGE 5 VERIFICATION WORKFLOW ===

@app.route("/request/<int:request_id>/verify", methods=["POST"])
def verify_request_route(request_id):
    """Verify a pending request (staff only)."""
    if not request.args.get("staff") == "1":
        return ("", 403)
    
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
    if not request.args.get("staff") == "1":
        return ("", 403)
    
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
    if not request.args.get("staff") == "1":
        return ("", 403)
    
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
    """Activate a request and send Wave 1 alerts (simulator channel)."""
    if not request.args.get("staff") == "1":
        return ("", 403)
    
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
    
    # Write Wave 1 alerts
    wave1_donors = plan["wave1"]
    for donor in wave1_donors:
        db.insert_alert(
            request_id=request_id,
            donor_id=donor["id"],
            wave_no=1,
            channel="simulator"
        )
    
    # Write audit log
    db.insert_audit_log(
        actor="staff_simulator",
        action="activate_request",
        entity="request",
        entity_id=request_id,
        detail=f"Activated with Wave 1: {len(wave1_donors)} donors, Wave 2: {len(plan['wave2'])} donors queued"
    )
    
    flash(f"Request activated! {len(wave1_donors)} donors alerted in Wave 1.", "success")
    return redirect(url_for("request_status", request_id=request_id, staff=1))

# === STAGE 4 SIMULATOR ===

@app.route("/request/<int:request_id>/advance", methods=["POST"])
def advance_simulation(request_id):
    """Advance the simulator: process pending replies and fire Wave 2 if needed."""
    if not request.args.get("staff") == "1":
        return ("", 403)
    
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
    
    # Process Wave 1 replies (seeded simulation)
    confirmed_count = 0
    for alert in wave1_alerts:
        if alert.get("reply") is None:
            # Simulate reply based on predictor score
            donor = db.get_donor(alert["donor_id"])
            
            # Get donor's predicted score from ranking
            # (For now, we'll use a simple placeholder; in real code, we'd store it)
            score = 0.5  # Neutral default
            
            reply = alerting.determine_reply(donor, score, seeded_rng)
            
            db.update_alert_reply(alert["id"], reply)
            if reply == "confirmed":
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
        
        for donor in wave2_donors:
            db.insert_alert(
                request_id=request_id,
                donor_id=donor["id"],
                wave_no=2,
                channel="simulator"
            )
        
        # Write audit log
        db.insert_audit_log(
            actor="simulator",
            action="fire_wave2",
            entity="request",
            entity_id=request_id,
            detail=f"Wave 1 had {confirmed_count}/{req.get('units', 1)} confirmations, firing Wave 2 with {len(wave2_donors)} donors"
        )
        
        flash(f"Wave 1 had {confirmed_count} confirmations (needed {req.get('units', 1)}). Firing Wave 2 with {len(wave2_donors)} donors.", "info")
    
    return redirect(url_for("request_status", request_id=request_id, staff=1))

@app.route("/request/<int:request_id>/donor/<int:donor_id>/mark-donated", methods=["POST"])
def mark_donated(request_id, donor_id):
    """Mark a confirmed donor as having donated."""
    if not request.args.get("staff") == "1":
        return ("", 403)
    
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
    if not request.args.get("staff") == "1":
        return ("", 403)
    
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
    if not request.args.get("staff") == "1":
        return ("", 403)
    
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
    if not request.args.get("staff") == "1":
        return ("", 403)
    
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

# === ERROR HANDLERS ===

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
