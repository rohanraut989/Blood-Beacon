"""
BloodBeacon — Emergency Blood-Donor Activation System
Flask application
"""

import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
import db

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

    return render_template("request_status.html", request=req)

# === STAGE 1 MATCH PREVIEW ===

@app.route("/match/<int:request_id>")
def match_preview(request_id):
    """Stage 1 match preview: exact blood group in same city only."""
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    req = db.get_request(request_id)
    if not req:
        flash("Request not found.", "error")
        return redirect(url_for("home"))

    # Get donors with exact blood group in same city
    donors = db.get_donors_by_group_and_city(req["blood_group"], req["city"])

    return render_template("match_preview.html", request=req, donors=donors, stage="Stage 1")

# === STAFF ===

@app.route("/staff")
def staff_dashboard():
    """Staff dashboard (placeholder for Stage 2)."""
    if not db.is_db_configured():
        flash("Database not configured.", "error")
        return redirect(url_for("home"))

    requests_list = db.get_all_requests()
    return render_template("staff_dashboard.html", requests=requests_list)

# === ERROR HANDLERS ===

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("500.html"), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
