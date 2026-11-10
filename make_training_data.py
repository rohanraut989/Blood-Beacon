"""
Generate synthetic training data for the donor response predictor.

SYNTHETIC RULE (DO NOT PRESENT AS REAL):
This version of BloodBeacon has no real alert history. The show-up probability
is generated from a synthetic rule for training purposes only:

- Base probability: 50%
- Increases by:
  - past_response_rate: +20% (if donor has responded before)
  - past_showup_rate: +20% (if donor has shown up before)
  - same_area: +10% (if alert in same geographic area)
  - days_since_last_donation > 60: +5% (well rested)
- Decreases by:
  - alerts_last_30d: -3% per alert (fatigue effect; max -15%)
  - days_since_last_donation < 5: -10% (too soon after donation)
  - hour_of_day < 8 or > 22: -5% (outside convenient hours)
- Final: add random noise ±10%, clamp to [0, 1]

This rule is PLAUSIBLE but NOT real. It will be replaced or extended with
actual alert outcomes in Stage 4+. The model's accuracy is advisory only.
"""

import csv
import random
from datetime import datetime

RANDOM_SEED = 42


def generate_training_data(output_path: str = "data/training_outcomes.csv", num_rows: int = 600):
    """
    Generate ~600 rows of synthetic past alert outcomes.
    
    Each row represents: one alert to one donor, with outcome (showed_up: 0/1).
    
    Args:
        output_path: where to write the CSV
        num_rows: number of rows to generate (default 600)
    """
    random.seed(RANDOM_SEED)
    
    rows = []
    
    for i in range(num_rows):
        # Feature: days since last donation (0 = just donated, 365+ = long ago)
        days_since_last_donation = random.randint(0, 365)
        
        # Feature: total number of donations in history
        total_donations = random.randint(0, 30)
        
        # Feature: number of alerts received in last 30 days
        alerts_last_30d = random.randint(0, 10)
        
        # Feature: historical response rate (0 = never replied, 1 = always replied)
        # New donors (total_donations == 0) get neutral 0.5
        past_response_rate = 0.5 if total_donations == 0 else random.random()
        
        # Feature: historical show-up rate (0 = never showed, 1 = always showed)
        # New donors get neutral 0.5
        past_showup_rate = 0.5 if total_donations == 0 else random.random()
        
        # Feature: same area as hospital (0 = different area, 1 = same area)
        same_area = random.randint(0, 1)
        
        # Feature: hour of day alert was sent (0..23)
        hour_of_day = random.randint(0, 23)
        
        # SYNTHETIC RULE: compute show-up probability
        prob = 0.5  # base
        
        prob += past_response_rate * 0.20
        prob += past_showup_rate * 0.20
        prob += same_area * 0.10
        
        if days_since_last_donation > 60:
            prob += 0.05
        
        if days_since_last_donation < 5:
            prob -= 0.10
        
        alert_fatigue = min(alerts_last_30d * 0.03, 0.15)
        prob -= alert_fatigue
        
        if hour_of_day < 8 or hour_of_day > 22:
            prob -= 0.05
        
        # Add random noise and clamp to [0, 1]
        noise = random.uniform(-0.10, 0.10)
        prob += noise
        prob = max(0.0, min(1.0, prob))
        
        # Generate label: showed_up based on probability
        showed_up = 1 if random.random() < prob else 0
        
        rows.append({
            "days_since_last_donation": days_since_last_donation,
            "total_donations": total_donations,
            "alerts_last_30d": alerts_last_30d,
            "past_response_rate": round(past_response_rate, 3),
            "past_showup_rate": round(past_showup_rate, 3),
            "same_area": same_area,
            "hour_of_day": hour_of_day,
            "showed_up": showed_up,
        })
    
    # Write CSV
    with open(output_path, "w", newline="") as f:
        fieldnames = [
            "days_since_last_donation",
            "total_donations",
            "alerts_last_30d",
            "past_response_rate",
            "past_showup_rate",
            "same_area",
            "hour_of_day",
            "showed_up",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✓ Generated {len(rows)} training rows to {output_path}")


if __name__ == "__main__":
    generate_training_data()
