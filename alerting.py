"""
Wave Alerting Engine — pure planner for BloodBeacon.

This module contains the logic for planning which donors to alert in each wave,
based on the Stage 3 ranking, anti-spam rules, and quiet hours.
"""

from datetime import datetime, time


def plan_waves(ranked_eligible, request, alerts_history, now):
    """
    Plan which donors to alert in Wave 1, Wave 2, and who to skip.
    
    Args:
        ranked_eligible: list of (donor, score, reason) from predictor.rank_donors()
        request: dict with keys like blood_group, city, units, needed_by
        alerts_history: dict { donor_id: [alert dict, ...] }
        now: datetime object (for quiet hours check)
    
    Returns:
        dict {
            "wave1": [donor, donor, ...],  # Top 10, each donor full dict from ranked_eligible
            "wave2": [donor, donor, ...],  # Next 20
            "skipped": [{"donor": donor, "reason": reason}, ...],
            "policy_note": str or None    # Note about quiet hours if applicable
        }
    """
    wave1 = []
    wave2 = []
    skipped = []
    policy_note = None
    
    # Check quiet hours (21:00-08:00): note it but don't block alerting in simulator
    current_hour = now.hour
    in_quiet_hours = current_hour >= 21 or current_hour < 8
    if in_quiet_hours:
        policy_note = f"Quiet hours (21:00-08:00): alerting at {now.strftime('%H:%M')} noted for real delivery policy (Stage 6)"
    
    # Build set of donors to skip due to monthly cap
    # A donor with 4+ alerts in last 30 days is skipped
    donors_at_cap = set()
    for donor_id, alerts in alerts_history.items():
        if not alerts:
            continue
        
        # Count alerts in last 30 days
        count_30d = 0
        for alert in alerts:
            alert_created = alert.get("created_at")
            if isinstance(alert_created, str):
                alert_date = datetime.strptime(alert_created, "%Y-%m-%d").date()
            else:
                alert_date = alert_created
            
            days_ago = (now.date() - alert_date).days
            if days_ago <= 30:
                count_30d += 1
        
        if count_30d >= 4:
            donors_at_cap.add(donor_id)
    
    # Process ranked eligible donors
    for donor, score, reason in ranked_eligible:
        donor_id = donor.get("id")
        
        # Check if donor is at monthly cap
        if donor_id in donors_at_cap:
            skipped.append({
                "donor": donor,
                "reason": "monthly cap"
            })
            continue
        
        # Assign to wave
        if len(wave1) < 10:
            wave1.append(donor)
        elif len(wave2) < 20:
            wave2.append(donor)
        # Anything beyond wave2 stays unalerted
    
    return {
        "wave1": wave1,
        "wave2": wave2,
        "skipped": skipped,
        "policy_note": policy_note
    }


def determine_reply(donor, score, seeded_rng):
    """
    Simulate a donor's reply based on their Stage 3 predicted show-up probability.
    
    Args:
        donor: donor dict
        score: float in [0, 1] from predictor
        seeded_rng: random.Random instance (seeded per-request for determinism)
    
    Returns:
        str: "confirmed", "declined", or "no_reply"
    """
    rand_val = seeded_rng.random()
    
    if rand_val < score:
        # Donor shows up: reply "confirmed"
        return "confirmed"
    elif rand_val < score + 0.2:
        # Donor declines (20% chance if didn't confirm)
        return "declined"
    else:
        # No reply
        return "no_reply"
