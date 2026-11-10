"""
BloodBeacon Compatibility Engine
Blood-type compatibility matrix for red blood cells, plasma, and platelets.
"""

# Red-cell compatibility matrix (standard blood donor compatibility)
# Key: donor blood group → set of recipient blood groups that can receive
# Note: O- is universal (can donate to all); AB+ is universal recipient (can receive from all)
# Rh factor: Rh- blood can only donate to Rh- recipients (safety); Rh+ can donate to Rh+
# ABO: O can donate to all; A can donate to A/AB; B can donate to B/AB; AB can donate to AB only
RED_CELL_COMPATIBILITY = {
    "O+": {"O+", "A+", "B+", "AB+"},
    "O-": {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"},  # Universal donor
    "A+": {"A+", "AB+"},
    "A-": {"A+", "A-", "AB+", "AB-"},
    "B+": {"B+", "AB+"},
    "B-": {"B+", "B-", "AB+", "AB-"},
    "AB+": {"AB+"},
    "AB-": {"AB+", "AB-"},
}

# Plasma compatibility matrix (INVERSE from RBC: based on donor plasma antibodies)
# NOTE: Rh factor DOES NOT matter for plasma transfusions
# AB plasma (no A/B antibodies): can go to ALL recipients (all Rh)
# A plasma (has B antibodies): can go to A and O recipients (all Rh)
# B plasma (has A antibodies): can go to B and O recipients (all Rh)
# O plasma (has A/B antibodies): can go to O recipients ONLY (all Rh)
# Key: donor blood group → set of recipient blood groups that can receive this plasma
PLASMA_COMPATIBILITY = {
    "AB+": {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"},  # AB to all (Rh-agnostic)
    "AB-": {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"},  # AB to all (Rh-agnostic)
    "A+": {"A+", "A-", "O+", "O-"},                               # A plasma to A and O
    "A-": {"A+", "A-", "O+", "O-"},                               # A plasma to A and O
    "B+": {"B+", "B-", "O+", "O-"},                               # B plasma to B and O
    "B-": {"B+", "B-", "O+", "O-"},                               # B plasma to B and O
    "O+": {"O+", "O-"},                                           # O to O only
    "O-": {"O+", "O-"},                                           # O to O only
}

# Platelet compatibility (v1 — using whole-blood matrix)
# TODO-verify: Platelet compatibility rules differ from whole blood (cross-matching
# guidelines are complex). In v1, we use the whole-blood matrix as a conservative
# approximation. Real implementation requires cross-matching.
PLATELET_COMPATIBILITY = RED_CELL_COMPATIBILITY.copy()


def compatible_donor_groups(recipient_group, component="whole_blood"):
    """
    Get all donor blood groups that can donate to a recipient.
    
    Args:
        recipient_group: str (e.g., "B+")
        component: str ("whole_blood" | "plasma" | "platelets")
    
    Returns:
        set of compatible donor blood groups
    
    Example:
        compatible_donor_groups("B+", "whole_blood") → {"B+", "B-", "O+", "O-"}
        compatible_donor_groups("AB+", "plasma") → {"AB+", "AB-"}
    """
    if component == "whole_blood":
        matrix = RED_CELL_COMPATIBILITY
    elif component == "plasma":
        matrix = PLASMA_COMPATIBILITY
    elif component == "platelets":
        # TODO-verify: See note above about platelet matching
        matrix = PLATELET_COMPATIBILITY
    else:
        raise ValueError(f"Unknown component: {component}")
    
    # Find all donors whose recipients include this recipient group
    compatible = set()
    for donor_group, recipients in matrix.items():
        if recipient_group in recipients:
            compatible.add(donor_group)
    
    return compatible


def get_all_blood_groups():
    """Return all 8 blood groups."""
    return {"O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"}


def is_compatible(donor_group, recipient_group, component="whole_blood"):
    """
    Check if a donor blood group can donate to a recipient.
    
    Args:
        donor_group: str
        recipient_group: str
        component: str ("whole_blood" | "plasma" | "platelets")
    
    Returns:
        bool
    """
    compatible = compatible_donor_groups(recipient_group, component)
    return donor_group in compatible
