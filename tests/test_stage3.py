"""
Tests for Stage 3: Donor Response Predictor
"""

import csv
import os
import hashlib
from datetime import date, datetime
from pathlib import Path

import pytest

from make_training_data import generate_training_data, RANDOM_SEED
from predictor import train_model, score_donor, rank_donors, load_model


class TestTrainingDataGenerator:
    """Verify synthetic training data generation is deterministic."""
    
    def test_csv_generates_deterministically(self):
        """Same seed should produce same file."""
        csv_path1 = "data/training_outcomes_test1.csv"
        csv_path2 = "data/training_outcomes_test2.csv"
        
        try:
            generate_training_data(csv_path1, num_rows=100)
            generate_training_data(csv_path2, num_rows=100)
            
            # Compute hashes
            with open(csv_path1, "rb") as f:
                hash1 = hashlib.md5(f.read()).hexdigest()
            with open(csv_path2, "rb") as f:
                hash2 = hashlib.md5(f.read()).hexdigest()
            
            assert hash1 == hash2, "Deterministic seed should produce identical files"
        
        finally:
            for p in [csv_path1, csv_path2]:
                if os.path.exists(p):
                    os.remove(p)
    
    def test_csv_has_correct_rows(self):
        """CSV should have ~600 rows plus header."""
        csv_path = "data/training_outcomes.csv"
        assert os.path.exists(csv_path), "Training data should exist"
        
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 600, f"Should have 600 rows, got {len(rows)}"
    
    def test_csv_has_both_labels(self):
        """CSV should have both showed_up=0 and showed_up=1."""
        csv_path = "data/training_outcomes.csv"
        
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            labels = set(int(row["showed_up"]) for row in reader)
        
        assert labels == {0, 1}, "Should have both labels (0 and 1)"


class TestModelTraining:
    """Verify model training and accuracy."""
    
    def test_model_trains_successfully(self):
        """Model should train without errors."""
        result = train_model()
        assert result is not None
        assert "model" in result
        assert "scaler" in result
        assert "accuracy" in result
        assert "baseline_accuracy" in result
    
    def test_model_accuracy_in_valid_range(self):
        """Accuracy should be in [0, 1]."""
        result = train_model()
        assert 0 <= result["accuracy"] <= 1
        assert 0 <= result["baseline_accuracy"] <= 1
    
    def test_model_beats_baseline(self):
        """Model should beat majority-class baseline."""
        result = train_model()
        assert result["accuracy"] > result["baseline_accuracy"], \
            f"Accuracy {result['accuracy']:.1%} should beat baseline {result['baseline_accuracy']:.1%}"
    
    def test_model_saved_and_loadable(self):
        """Model should be saved to disk and loadable."""
        model_path = "models/predictor.joblib"
        assert os.path.exists(model_path), f"Model should exist at {model_path}"
        
        model_data = load_model(model_path)
        assert "model" in model_data
        assert "scaler" in model_data
        assert "feature_names" in model_data


class TestScoring:
    """Verify donor scoring."""
    
    def test_score_donor_returns_probability(self):
        """Score should be in [0, 1]."""
        features = {
            "days_since_last_donation": 100,
            "total_donations": 5,
            "alerts_last_30d": 2,
            "past_response_rate": 0.8,
            "past_showup_rate": 0.9,
            "same_area": 1,
            "hour_of_day": 14,
        }
        score = score_donor(features)
        assert isinstance(score, float)
        assert 0 <= score <= 1, f"Score {score} should be in [0, 1]"
    
    def test_new_donor_gets_midrange_score(self):
        """Brand-new donor (no history) should get reasonable score, not minimum."""
        features = {
            "days_since_last_donation": 365,  # Never donated
            "total_donations": 0,
            "alerts_last_30d": 0,
            "past_response_rate": 0.5,  # Neutral
            "past_showup_rate": 0.5,   # Neutral
            "same_area": 0,
            "hour_of_day": 14,
        }
        score = score_donor(features)
        
        # Should be in reasonable range, not close to 0 (showing we don't penalize new donors)
        assert score > 0.3, f"New donor score {score} should be reasonable, not minimum"
        assert score < 1.0, f"New donor score {score} should be a probability"


class TestRanking:
    """Verify donor ranking."""
    
    def test_ranking_fixture_a_beats_b(self):
        """
        Donor A (same area, high rates, no recent alerts, well-rested)
        should rank above Donor B (different area, low rates, many alerts, recently donated).
        """
        request = {
            "blood_group": "O+",
            "city": "Kathmandu",
            "area": "Thamel",
            "needed_by": "2026-11-10",
        }
        
        # Donor A: strong candidate
        donor_a = {
            "id": 1,
            "name": "Reliable Alice",
            "blood_group": "O+",
            "city": "Kathmandu",
            "area": "Thamel",
        }
        
        # Donor B: weak candidate
        donor_b = {
            "id": 2,
            "name": "Fatigued Bob",
            "blood_group": "O+",
            "city": "Kathmandu",
            "area": "Bhaktapur",  # Different area
        }
        
        today = date(2026, 11, 10)
        
        # Donations: A has old donations (well-rested), B donated recently
        donations_by_donor = {
            1: [{"donated_on": date(2026, 7, 1)}],  # 100+ days ago
            2: [{"donated_on": date(2026, 11, 6)}],  # 4 days ago
        }
        
        # Alerts: A has few recent alerts, B has many
        alerts_by_donor = {
            1: [],  # No recent alerts
            2: [
                {"created_at": date(2026, 11, 9)},
                {"created_at": date(2026, 11, 8)},
                {"created_at": date(2026, 11, 7)},
                {"created_at": date(2026, 11, 6)},
                {"created_at": date(2026, 11, 5)},
                {"created_at": date(2026, 11, 4)},
            ],  # 6 alerts in 30 days
        }
        
        ranked = rank_donors(
            request,
            [donor_a, donor_b],
            donations_by_donor,
            alerts_by_donor,
            today
        )
        
        assert ranked[0][0]["id"] == 1, f"Donor A should rank first, got {ranked[0][0]['name']}"
        assert ranked[1][0]["id"] == 2, f"Donor B should rank second, got {ranked[1][0]['name']}"
    
    def test_ranking_returns_score_and_reason(self):
        """Each ranking entry should have donor, score, and reason."""
        request = {
            "blood_group": "O+",
            "city": "Kathmandu",
            "area": "Thamel",
        }
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "O+",
            "city": "Kathmandu",
            "area": "Thamel",
        }
        
        today = date(2026, 11, 10)
        donations_by_donor = {1: [{"donated_on": date(2026, 7, 1)}]}
        alerts_by_donor = {1: []}
        
        ranked = rank_donors(request, [donor], donations_by_donor, alerts_by_donor, today)
        
        assert len(ranked) == 1
        donor_result, score, reason = ranked[0]
        
        assert donor_result["id"] == 1
        assert isinstance(score, float)
        assert 0 <= score <= 1
        assert isinstance(reason, str)
        assert len(reason) > 0
