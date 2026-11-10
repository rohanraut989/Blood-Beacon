"""
BloodBeacon Eligibility Engine
Assesses donor eligibility based on NBTC rules.
Pure, unit-testable function: assess_donor(donor, donations, rules, today)
"""

from datetime import datetime, date

def assess_donor(donor, donations, rules, today):
    """
    Assess whether a donor is eligible to donate today.
    
    Args:
        donor: dict with keys {id, name, blood_group, gender, date_of_birth, weight_kg, ...}
        donations: list of dict with keys {id, donor_id, donated_on, ...}
        rules: dict mapping rule key to value
               Expected keys: age_min, age_max, weight_min_kg, hemoglobin_min,
                             donation_gap_men_days, donation_gap_women_days
        today: date object (for testability)
    
    Returns:
        dict: {
            "status": "eligible" | "deferred",
            "eligible_on": date | None,
            "reasons": [str]
        }
    """
    reasons = []
    eligible = True
    eligible_on = None
    
    # Parse dates
    if isinstance(today, str):
        today = datetime.strptime(today, "%Y-%m-%d").date()
    if isinstance(donor.get("date_of_birth"), str):
        dob = datetime.strptime(donor["date_of_birth"], "%Y-%m-%d").date()
    else:
        dob = donor["date_of_birth"]
    
    # === 1. AGE CHECK ===
    age_min = int(rules.get("age_min", 18))
    age_max = int(rules.get("age_max", 65))
    
    age = (today - dob).days // 365  # Simple age calculation
    
    if age < age_min:
        eligible = False
        reasons.append(f"Age {age} is below minimum {age_min} years")
    elif age > age_max:
        eligible = False
        reasons.append(f"Age {age} exceeds maximum {age_max} years")
    
    # === 2. WEIGHT CHECK ===
    weight_min_kg = float(rules.get("weight_min_kg", 45))
    weight_kg = float(donor.get("weight_kg", 0))
    
    if weight_kg < weight_min_kg:
        eligible = False
        reasons.append(f"Weight {weight_kg}kg is below minimum {weight_min_kg}kg")
    
    # === 3. DONATION GAP CHECK ===
    # Find latest donation
    if donations:
        # Sort by donated_on descending, get most recent
        sorted_donations = sorted(
            donations,
            key=lambda d: d.get("donated_on", ""),
            reverse=True
        )
        latest_donation = sorted_donations[0]
        
        # Parse donation date
        if isinstance(latest_donation["donated_on"], str):
            last_donation_date = datetime.strptime(
                latest_donation["donated_on"],
                "%Y-%m-%d"
            ).date()
        else:
            last_donation_date = latest_donation["donated_on"]
        
        # Determine gap requirement based on gender
        if donor.get("gender") == "Female":
            gap_days = int(rules.get("donation_gap_women_days", 120))
        else:
            gap_days = int(rules.get("donation_gap_men_days", 90))
        
        # Calculate days since last donation
        days_since = (today - last_donation_date).days
        
        if days_since < gap_days:
            eligible = False
            eligible_on = last_donation_date + __timedelta_from_days(gap_days)
            gender_str = "women" if donor.get("gender") == "Female" else "men"
            reasons.append(
                f"Only {days_since} days since last donation; "
                f"{gap_days} days required for {gender_str}"
            )
    
    # === 4. TODO: UNVERIFIED DEFERRALS ===
    # Deferrals that need data not currently in schema:
    # - Tattoo/piercing (tattoo_date field needed)
    # - Major surgery (surgery_date, surgery_type fields needed)
    # - Pregnancy (pregnancy_status field needed)
    # - Recent fever/antibiotics (recent_fever, recent_antibiotics fields needed)
    # These are marked TODO-verify in the context and remain unimplemented.
    
    # === 5. HEMOGLOBIN CHECK (TODO) ===
    # Would check: hemoglobin_level >= hemoglobin_min
    # But hemoglobin_level is not collected in donor registration
    # Data not available; marked as TODO-verify
    
    return {
        "status": "eligible" if eligible else "deferred",
        "eligible_on": eligible_on,
        "reasons": reasons
    }


def __timedelta_from_days(days):
    """Helper to create a timedelta from days (for Python date arithmetic)."""
    from datetime import timedelta
    return timedelta(days=days)
