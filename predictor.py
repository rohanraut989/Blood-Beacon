"""
Donor Response Predictor — scikit-learn LogisticRegression model.

This model is trained on synthetic history (see make_training_data.py).
It predicts the probability that a donor will show up in response to an alert.

IMPORTANT: This is synthetic training data. Predictions are advisory only
and will improve with real alert outcomes in Stage 4+.
"""

import csv
import joblib
import os
from datetime import date, datetime
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler
from utils import parse_date

MODEL_PATH = "models/predictor.joblib"
TRAINING_DATA_PATH = "data/training_outcomes.csv"
RANDOM_SEED = 42


def train_model(training_data_path: str = TRAINING_DATA_PATH, model_path: str = MODEL_PATH):
    """
    Train LogisticRegression on synthetic training data.
    
    Args:
        training_data_path: path to CSV with features and labels
        model_path: where to save the trained model
    
    Returns:
        dict with keys: model, scaler, accuracy, baseline_accuracy, feature_names
    """
    # Load CSV
    if not os.path.exists(training_data_path):
        raise FileNotFoundError(f"Training data not found: {training_data_path}")
    
    X = []
    y = []
    feature_names = [
        "days_since_last_donation",
        "total_donations",
        "alerts_last_30d",
        "past_response_rate",
        "past_showup_rate",
        "same_area",
        "hour_of_day",
    ]
    
    with open(training_data_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            features = [
                float(row["days_since_last_donation"]),
                float(row["total_donations"]),
                float(row["alerts_last_30d"]),
                float(row["past_response_rate"]),
                float(row["past_showup_rate"]),
                float(row["same_area"]),
                float(row["hour_of_day"]),
            ]
            X.append(features)
            y.append(int(row["showed_up"]))
    
    X = np.array(X)
    y = np.array(y)
    
    # Normalize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=RANDOM_SEED
    )
    
    # Train model
    model = LogisticRegression(random_state=RANDOM_SEED, max_iter=1000)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    # Baseline: always predict majority class
    baseline_accuracy = max(y_test.mean(), 1 - y_test.mean())
    
    print(f"✓ Model trained")
    print(f"  Held-out accuracy: {accuracy:.1%}")
    print(f"  Baseline accuracy: {baseline_accuracy:.1%}")
    print(f"  Beats baseline: {'✓' if accuracy > baseline_accuracy else '✗'}")
    
    # Save model and scaler
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": model,
        "scaler": scaler,
        "feature_names": feature_names
    }, model_path)
    print(f"✓ Model saved to {model_path}")
    
    return {
        "model": model,
        "scaler": scaler,
        "accuracy": accuracy,
        "baseline_accuracy": baseline_accuracy,
        "feature_names": feature_names,
    }


def load_model(model_path: str = MODEL_PATH):
    """Load trained model from disk."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}. Run train_model() first.")
    return joblib.load(model_path)


def score_donor(features: dict) -> float:
    """
    Predict show-up probability for a donor given their features.
    
    Args:
        features: dict with keys matching feature_names from training
                 (days_since_last_donation, total_donations, alerts_last_30d,
                  past_response_rate, past_showup_rate, same_area, hour_of_day)
    
    Returns:
        float in [0, 1]: predicted probability of showing up
    """
    model_data = load_model()
    model = model_data["model"]
    scaler = model_data["scaler"]
    feature_names = model_data["feature_names"]
    
    # Extract features in order and scale
    X = np.array([[features.get(name, 0.5) for name in feature_names]])
    X_scaled = scaler.transform(X)
    
    # Predict probability of class 1 (showed_up)
    prob = model.predict_proba(X_scaled)[0][1]
    return float(prob)


def rank_donors(request, eligible_donors, donations_by_donor, alerts_by_donor, today):
    """
    Rank eligible donors by predicted show-up probability.
    
    Args:
        request: dict with keys like blood_group, city, needed_by
        eligible_donors: list of donor dicts (with id, name, blood_group, city, area)
        donations_by_donor: dict { donor_id: [donation dict, ...] }
        alerts_by_donor: dict { donor_id: [alert dict, ...] }
        today: date object for time calculations
    
    Returns:
        list of (donor, score, reason) sorted best-first.
        donor: the donor dict
        score: float in [0, 1]
        reason: str, one short human phrase explaining the strongest factor
    """
    # Current hour for features (assume alerts sent now)
    current_hour = datetime.now().hour
    
    ranked = []
    
    for donor in eligible_donors:
        donor_id = donor.get("id")
        
        # Gather features
        donations = donations_by_donor.get(donor_id, [])
        alerts = alerts_by_donor.get(donor_id, [])
        
        # days_since_last_donation
        if donations:
            # Sort by date descending, get most recent
            sorted_dons = sorted(
                donations,
                key=lambda d: d.get("donated_on", ""),
                reverse=True
            )
            last_donation = sorted_dons[0]
            
            last_donation_date = parse_date(last_donation.get("donated_on", today))
            
            days_since = (today - last_donation_date).days
        else:
            days_since = 365  # Never donated = long ago
        
        # total_donations
        total_donations = len(donations)
        
        # alerts_last_30d
        alerts_last_30d = 0
        if alerts:
            for alert in alerts:
                alert_date_str = alert.get("created_at", "")
                alert_date = parse_date(alert_date_str)
                
                days_ago = (today - alert_date).days
                if days_ago <= 30:
                    alerts_last_30d += 1
        
        # past_response_rate and past_showup_rate
        # For now, treat "responses" as replies to alerts and "showup" as donations
        # New donors (no donations) get neutral 0.5
        if total_donations == 0:
            past_response_rate = 0.5
            past_showup_rate = 0.5
        else:
            # Simplification: assume response_rate = showup_rate ≈ donation frequency / alerts
            past_showup_rate = min(total_donations / max(1, alerts_last_30d + 3), 1.0)
            past_response_rate = past_showup_rate
        
        # same_area
        same_area = 1 if donor.get("area") == request.get("area") else 0
        # Fallback: if city matches, assume same area
        if not same_area and donor.get("city") == request.get("city"):
            same_area = 1
        
        # hour_of_day
        hour_of_day = current_hour
        
        # Predict
        features = {
            "days_since_last_donation": days_since,
            "total_donations": total_donations,
            "alerts_last_30d": alerts_last_30d,
            "past_response_rate": past_response_rate,
            "past_showup_rate": past_showup_rate,
            "same_area": same_area,
            "hour_of_day": hour_of_day,
        }
        
        try:
            score = score_donor(features)
        except Exception as error:
            # Predictor output is advisory; a model/data issue must not erase
            # an otherwise eligible donor from the matching pool.
            print(
                f"Predictor fallback for donor {donor_id}: {type(error).__name__}: {error}"
            )
            score = 0.5
        if not np.isfinite(score):
            print(f"Predictor fallback for donor {donor_id}: non-finite score {score!r}")
            score = 0.5
        
        # Determine reason: strongest positive or main drag
        reason = _score_reason(features, past_response_rate, past_showup_rate)
        
        ranked.append((donor, score, reason))
    
    # Sort by score descending (best first)
    ranked.sort(key=lambda x: x[1], reverse=True)
    
    return ranked


def _score_reason(features, past_response_rate, past_showup_rate) -> str:
    """
    Return a short human reason for the score based on the strongest factor.
    
    Returns one of:
    - "replies often" (high past_response_rate)
    - "shows up reliably" (high past_showup_rate)
    - "same area" (same_area == 1)
    - "well rested" (days_since_last_donation > 60)
    - "recently alerted" (high alerts_last_30d, fatigue)
    - "alerted often recently" (alerts_last_30d >= 5, fatigue)
    - "too soon after donation" (days_since < 5)
    - "outside convenient hours" (hour < 8 or > 22)
    - "neutral history" (new donor)
    """
    days_since = features.get("days_since_last_donation", 0)
    alerts_last_30d = features.get("alerts_last_30d", 0)
    same_area = features.get("same_area", 0)
    hour = features.get("hour_of_day", 12)
    
    # Check main drags first (negatives dominate perception)
    if alerts_last_30d >= 5:
        return "alerted often recently"
    
    if days_since < 5:
        return "too soon after donation"
    
    if hour < 8 or hour > 22:
        return "outside convenient hours"
    
    # Then check positives
    if past_showup_rate >= 0.8:
        return "shows up reliably"
    
    if past_response_rate >= 0.8:
        return "replies often"
    
    if same_area == 1:
        return "same area"
    
    if days_since > 60:
        return "well rested"
    
    return "neutral history"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--train":
        train_model()
    else:
        print("Usage: python predictor.py --train")
        print("Or import and use: train_model(), score_donor(), rank_donors()")
