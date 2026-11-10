"""
BloodBeacon Tests - Stage 2
Tests for eligibility and compatibility engines.
Run with: pytest tests/test_stage2.py -v
"""

import pytest
import sys
import os
from datetime import datetime, date, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import eligibility
import compatibility


class TestEligibilityEngine:
    """Tests for the eligibility assessment engine."""
    
    def get_rules(self):
        """Standard NBTC rules for testing."""
        return {
            "age_min": "18",
            "age_max": "65",
            "weight_min_kg": "45",
            "hemoglobin_min": "12.5",
            "donation_gap_men_days": "90",
            "donation_gap_women_days": "120",
        }
    
    def test_eligible_donor_no_donations(self):
        """Test that a donor with no donations is eligible (if age/weight pass)."""
        today = date(2024, 11, 10)
        dob = date(1990, 5, 15)  # Age 34
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "B+",
            "gender": "Male",
            "date_of_birth": dob,
            "weight_kg": 70.0,
        }
        
        result = eligibility.assess_donor(donor, [], self.get_rules(), today)
        
        assert result["status"] == "eligible"
        assert result["eligible_on"] is None
        assert result["reasons"] == []
    
    def test_man_60_days_after_donation_is_deferred(self):
        """Test that a man 60 days after donation is deferred (needs 90 days)."""
        today = date(2024, 11, 10)
        last_donation = date(2024, 9, 11)  # 60 days ago
        dob = date(1990, 5, 15)
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "B+",
            "gender": "Male",
            "date_of_birth": dob,
            "weight_kg": 70.0,
        }
        
        donations = [
            {
                "id": 1,
                "donor_id": 1,
                "donated_on": last_donation,
                "units": 1.0,
            }
        ]
        
        result = eligibility.assess_donor(donor, donations, self.get_rules(), today)
        
        assert result["status"] == "deferred"
        assert result["eligible_on"] is not None
        # Eligible on should be last_donation + 90 days = 2024-09-11 + 90 = 2024-12-10
        expected_eligible_on = date(2024, 12, 10)
        assert result["eligible_on"] == expected_eligible_on
        assert len(result["reasons"]) > 0
        assert "90 days required" in result["reasons"][0] or "gap" in result["reasons"][0].lower()
    
    def test_woman_130_days_after_donation_is_eligible(self):
        """Test that a woman 130 days after donation is eligible (needs 120 days)."""
        today = date(2024, 11, 10)
        last_donation = date(2024, 7, 2)  # 131 days ago
        dob = date(1990, 5, 15)
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "B+",
            "gender": "Female",
            "date_of_birth": dob,
            "weight_kg": 65.0,
        }
        
        donations = [
            {
                "id": 1,
                "donor_id": 1,
                "donated_on": last_donation,
                "units": 1.0,
            }
        ]
        
        result = eligibility.assess_donor(donor, donations, self.get_rules(), today)
        
        assert result["status"] == "eligible"
        assert result["eligible_on"] is None
        assert result["reasons"] == []
    
    def test_donor_age_17_is_deferred(self):
        """Test that a 17-year-old is deferred."""
        today = date(2024, 11, 10)
        dob = date(2007, 11, 11)  # Will be 17 on Nov 10, 2024
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "B+",
            "gender": "Male",
            "date_of_birth": dob,
            "weight_kg": 70.0,
        }
        
        result = eligibility.assess_donor(donor, [], self.get_rules(), today)
        
        assert result["status"] == "deferred"
        assert "Age" in result["reasons"][0] or "18" in result["reasons"][0]
    
    def test_donor_age_66_is_deferred(self):
        """Test that a 66-year-old is deferred."""
        today = date(2024, 11, 10)
        dob = date(1958, 11, 9)  # Will be 66 on Nov 10, 2024
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "B+",
            "gender": "Male",
            "date_of_birth": dob,
            "weight_kg": 70.0,
        }
        
        result = eligibility.assess_donor(donor, [], self.get_rules(), today)
        
        assert result["status"] == "deferred"
        assert "Age" in result["reasons"][0] or "65" in result["reasons"][0]
    
    def test_donor_weight_44kg_is_deferred(self):
        """Test that a 44kg donor is deferred (min 45kg)."""
        today = date(2024, 11, 10)
        dob = date(1990, 5, 15)
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "B+",
            "gender": "Female",
            "date_of_birth": dob,
            "weight_kg": 44.0,
        }
        
        result = eligibility.assess_donor(donor, [], self.get_rules(), today)
        
        assert result["status"] == "deferred"
        assert "Weight" in result["reasons"][0] or "45" in result["reasons"][0]
    
    def test_donor_weight_45kg_is_eligible(self):
        """Test that a 45kg donor at minimum weight is eligible."""
        today = date(2024, 11, 10)
        dob = date(1990, 5, 15)
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "B+",
            "gender": "Female",
            "date_of_birth": dob,
            "weight_kg": 45.0,
        }
        
        result = eligibility.assess_donor(donor, [], self.get_rules(), today)
        
        assert result["status"] == "eligible"
        assert result["reasons"] == []
    
    def test_multiple_deferrals_all_listed(self):
        """Test that multiple deferral reasons are all listed."""
        today = date(2024, 11, 10)
        dob = date(2007, 11, 11)  # Age 17
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "B+",
            "gender": "Male",
            "date_of_birth": dob,
            "weight_kg": 44.0,  # Below minimum
        }
        
        result = eligibility.assess_donor(donor, [], self.get_rules(), today)
        
        assert result["status"] == "deferred"
        assert len(result["reasons"]) >= 2  # At least age and weight reasons
    
    def test_woman_90_days_after_donation_is_deferred(self):
        """Test that a woman 90 days after donation is deferred (needs 120 days)."""
        today = date(2024, 11, 10)
        last_donation = date(2024, 8, 12)  # 90 days ago
        dob = date(1990, 5, 15)
        
        donor = {
            "id": 1,
            "name": "Test Donor",
            "blood_group": "B+",
            "gender": "Female",
            "date_of_birth": dob,
            "weight_kg": 65.0,
        }
        
        donations = [
            {
                "id": 1,
                "donor_id": 1,
                "donated_on": last_donation,
                "units": 1.0,
            }
        ]
        
        result = eligibility.assess_donor(donor, donations, self.get_rules(), today)
        
        assert result["status"] == "deferred"
        assert result["eligible_on"] is not None
        assert "120 days" in result["reasons"][0] or "days required for women" in result["reasons"][0]
    
    def test_eligible_on_is_date_for_time_based_deferrals(self):
        """eligible_on should be a DATE for time-based deferrals (age, donation gap)."""
        # Age deferral: should have eligible_on as 18th birthday
        today = date(2024, 11, 10)
        dob = date(2010, 3, 15)  # Age 14
        
        donor = {
            "id": 1,
            "name": "Young Donor",
            "blood_group": "O+",
            "gender": "Male",
            "date_of_birth": dob,
            "weight_kg": 70.0,
        }
        
        result = eligibility.assess_donor(donor, [], self.get_rules(), today)
        assert result["status"] == "deferred"
        assert result["eligible_on"] is not None
        assert isinstance(result["eligible_on"], date)
        assert result["eligible_on"] == date(2028, 3, 15)  # 18th birthday
    
    def test_eligible_on_is_none_for_weight_deferral(self):
        """eligible_on should be None for weight deferral (permanent condition)."""
        today = date(2024, 11, 10)
        dob = date(1990, 5, 15)  # Age 34
        
        donor = {
            "id": 1,
            "name": "Light Donor",
            "blood_group": "O+",
            "gender": "Male",
            "date_of_birth": dob,
            "weight_kg": 40.0,  # Below minimum 45kg
        }
        
        result = eligibility.assess_donor(donor, [], self.get_rules(), today)
        assert result["status"] == "deferred"
        assert "Weight" in result["reasons"][0]
        assert result["eligible_on"] is None  # No eligible_on for weight
    
    def test_eligible_on_is_none_for_over_65_deferral(self):
        """eligible_on should be None for age > 65 deferral (permanent condition)."""
        today = date(2024, 11, 10)
        dob = date(1940, 5, 15)  # Age 84
        
        donor = {
            "id": 1,
            "name": "Elderly Donor",
            "blood_group": "O+",
            "gender": "Male",
            "date_of_birth": dob,
            "weight_kg": 70.0,
        }
        
        result = eligibility.assess_donor(donor, [], self.get_rules(), today)
        assert result["status"] == "deferred"
        assert "exceeds maximum" in result["reasons"][0]
        assert result["eligible_on"] is None  # No eligible_on for age > max


class TestCompatibilityEngine:
    """Tests for blood-type compatibility."""
    
    def test_O_negative_is_universal_donor_whole_blood(self):
        """O- can donate to all blood groups (whole blood)."""
        compatible = compatibility.compatible_donor_groups("AB+", "whole_blood")
        assert "O-" in compatible
        assert "O+" in compatible  # O+ also compatible
        
        # Verify O- is universal
        for group in compatibility.get_all_blood_groups():
            assert compatibility.is_compatible("O-", group, "whole_blood")
    
    def test_AB_positive_is_universal_recipient_whole_blood(self):
        """AB+ can receive from all blood groups (whole blood)."""
        for donor_group in compatibility.get_all_blood_groups():
            assert compatibility.is_compatible(donor_group, "AB+", "whole_blood")
    
    def test_B_positive_compatibility(self):
        """B+ can receive from B+, B-, O+, O-."""
        expected_donors = {"B+", "B-", "O+", "O-"}
        compatible = compatibility.compatible_donor_groups("B+", "whole_blood")
        assert compatible == expected_donors
    
    def test_A_positive_compatibility(self):
        """A+ can receive from A+, A-, O+, O-."""
        expected_donors = {"A+", "A-", "O+", "O-"}
        compatible = compatibility.compatible_donor_groups("A+", "whole_blood")
        assert compatible == expected_donors
    
    def test_AB_negative_compatibility(self):
        """AB- can receive from AB-, A-, B-, O-."""
        expected_donors = {"AB-", "A-", "B-", "O-"}
        compatible = compatibility.compatible_donor_groups("AB-", "whole_blood")
        assert compatible == expected_donors
    
    def test_O_negative_cannot_receive_from_positive(self):
        """O- (negative blood) cannot receive from O+ (positive blood)."""
        # O- can only receive from O-
        assert not compatibility.is_compatible("O+", "O-", "whole_blood")
        assert not compatibility.is_compatible("A+", "O-", "whole_blood")
        assert compatibility.is_compatible("O-", "O-", "whole_blood")
    
    def test_AB_positive_plasma_compatibility(self):
        """AB plasma is universal (no A/B antigens). Rh-agnostic."""
        # AB+ can donate plasma to ALL recipients (A, B, O, AB; any Rh)
        recipients_for_ab_plus = compatibility.compatible_donor_groups("A+", "plasma")
        assert "AB+" in recipients_for_ab_plus
        recipients_for_o_minus = compatibility.compatible_donor_groups("O-", "plasma")
        assert "AB+" in recipients_for_o_minus
        recipients_for_b_minus = compatibility.compatible_donor_groups("B-", "plasma")
        assert "AB+" in recipients_for_b_minus
    
    def test_O_plasma_not_universal(self):
        """O plasma can ONLY go to O recipients (has A and B antibodies)."""
        # O can only donate to O (not A, not B, not AB)
        assert "O-" in compatibility.compatible_donor_groups("O+", "plasma")
        assert "O-" in compatibility.compatible_donor_groups("O-", "plasma")
        assert "O+" in compatibility.compatible_donor_groups("O-", "plasma")  # O- plasma to O+
        
        # O cannot donate to A, B, or AB
        assert "O+" not in compatibility.compatible_donor_groups("A+", "plasma")
        assert "O-" not in compatibility.compatible_donor_groups("B+", "plasma")
        assert "O+" not in compatibility.compatible_donor_groups("AB-", "plasma")
    
    def test_A_plasma_compatibility(self):
        """A plasma can go to A and O (no B antibodies in A plasma)."""
        # A plasma to A recipients
        assert "A+" in compatibility.compatible_donor_groups("A+", "plasma")
        assert "A-" in compatibility.compatible_donor_groups("A-", "plasma")
        
        # A plasma to O recipients
        assert "A+" in compatibility.compatible_donor_groups("O+", "plasma")
        assert "A-" in compatibility.compatible_donor_groups("O-", "plasma")
        
        # A plasma NOT to B or AB
        assert "A+" not in compatibility.compatible_donor_groups("B+", "plasma")
        assert "A-" not in compatibility.compatible_donor_groups("AB-", "plasma")
    
    def test_B_plasma_compatibility(self):
        """B plasma can go to B and O (no A antibodies in B plasma)."""
        # B plasma to B recipients
        assert "B+" in compatibility.compatible_donor_groups("B+", "plasma")
        assert "B-" in compatibility.compatible_donor_groups("B-", "plasma")
        
        # B plasma to O recipients
        assert "B+" in compatibility.compatible_donor_groups("O+", "plasma")
        assert "B-" in compatibility.compatible_donor_groups("O-", "plasma")
        
        # B plasma NOT to A or AB
        assert "B+" not in compatibility.compatible_donor_groups("A+", "plasma")
        assert "B-" not in compatibility.compatible_donor_groups("AB-", "plasma")
    
    def test_all_blood_groups_have_compatibility(self):
        """All 8 blood groups should have defined compatibility."""
        all_groups = compatibility.get_all_blood_groups()
        assert len(all_groups) == 8
        
        for group in all_groups:
            # Should always have at least one compatible donor (self)
            compatible = compatibility.compatible_donor_groups(group, "whole_blood")
            assert len(compatible) > 0
            assert group in compatible or any(
                compatibility.is_compatible(donor, group, "whole_blood")
                for donor in all_groups
            )
    
    def test_red_cell_compatibility_full_table(self):
        """Verify the entire red-cell compatibility matrix against canonical chart.
        
        Source: Standard blood transfusion compatibility (ABO + Rh system)
        - O- is universal donor (can donate to all 8 types)
        - AB+ is universal recipient (receives from all 8 types)
        - ABO compatibility: O→all, A→A/AB, B→B/AB, AB→AB only
        - Rh compatibility: Rh- can only receive from Rh-; Rh+ can receive from both
        
        Test verifies: for each DONOR, all recipients in the matrix can receive from that donor.
        """
        # Canonical red-cell chart: donor -> {recipients}
        canonical = {
            "O-": {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"},  # Universal
            "O+": {"O+", "A+", "B+", "AB+"},  # O to Rh+ only
            "A-": {"A-", "A+", "AB-", "AB+"},  # A to Rh- and Rh+
            "A+": {"A+", "AB+"},  # A to Rh+ only
            "B-": {"B-", "B+", "AB-", "AB+"},  # B to Rh- and Rh+
            "B+": {"B+", "AB+"},  # B to Rh+ only
            "AB-": {"AB-", "AB+"},  # AB to Rh- and Rh+
            "AB+": {"AB+"},  # AB to Rh+ only
        }
        
        # Verify each donor's recipients
        for donor in sorted(canonical.keys()):
            expected_recipients = canonical[donor]
            # For each recipient in expected, verify donor can donate to it
            for recipient in expected_recipients:
                actual_donors = compatibility.compatible_donor_groups(recipient, "whole_blood")
                assert donor in actual_donors, \
                    f"Mismatch: {donor} should be able to donate to {recipient}"
            
            # Also verify donors NOT in expected cannot donate
            all_groups = compatibility.get_all_blood_groups()
            not_expected = set(all_groups) - expected_recipients
            for non_recipient in not_expected:
                actual_donors = compatibility.compatible_donor_groups(non_recipient, "whole_blood")
                assert donor not in actual_donors, \
                    f"Mismatch: {donor} should NOT be able to donate to {non_recipient}"
    
    def test_platelets_uses_whole_blood_matrix_v1(self):
        """v1 platelets use whole-blood compatibility matrix (TODO-verify)."""
        # Both should match in v1
        compatible_whole = compatibility.compatible_donor_groups("B+", "whole_blood")
        compatible_platelets = compatibility.compatible_donor_groups("B+", "platelets")
        assert compatible_whole == compatible_platelets


class TestIntegrationEligibilityCompatibility:
    """Integration tests combining eligibility and compatibility."""
    
    def test_b_plus_request_with_o_plus_o_minus_donors(self):
        """B+ request in a city with only O+ and O- donors returns those donors."""
        today = date(2024, 11, 10)
        rules = {
            "age_min": "18",
            "age_max": "65",
            "weight_min_kg": "45",
            "donation_gap_men_days": "90",
            "donation_gap_women_days": "120",
        }
        
        # Recipient request: B+
        recipient_group = "B+"
        compatible_donors = compatibility.compatible_donor_groups(recipient_group, "whole_blood")
        
        # Should include O+ and O-
        assert "O+" in compatible_donors
        assert "O-" in compatible_donors
        
        # Test donors
        o_plus_donor = {
            "id": 1,
            "name": "O+ Donor",
            "blood_group": "O+",
            "gender": "Male",
            "date_of_birth": date(1990, 5, 15),
            "weight_kg": 70.0,
        }
        
        o_minus_donor = {
            "id": 2,
            "name": "O- Donor",
            "blood_group": "O-",
            "gender": "Female",
            "date_of_birth": date(1992, 7, 20),
            "weight_kg": 65.0,
        }
        
        # Both should be eligible
        result1 = eligibility.assess_donor(o_plus_donor, [], rules, today)
        result2 = eligibility.assess_donor(o_minus_donor, [], rules, today)
        
        assert result1["status"] == "eligible"
        assert result2["status"] == "eligible"
        
        # Both should be compatible with B+ request
        assert compatibility.is_compatible("O+", "B+", "whole_blood")
        assert compatibility.is_compatible("O-", "B+", "whole_blood")


class TestStage1Compatibility:
    """Verify that Stage 1 tests still pass (backward compatibility)."""
    
    def test_seed_covers_all_blood_groups(self):
        """Verify all 8 blood groups are in compatibility matrix."""
        all_groups = compatibility.get_all_blood_groups()
        expected = {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"}
        assert all_groups == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
