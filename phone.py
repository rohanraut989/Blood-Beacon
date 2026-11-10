"""Phone-number normalization for donor WhatsApp routing."""

import re


COUNTRY_CODES = {
    "91": "91",
    "+91": "91",
    "IN": "91",
    "977": "977",
    "+977": "977",
    "NP": "977",
}


def normalize_phone(country, national):
    """Return a digits-only international number for India or Nepal."""
    code = COUNTRY_CODES.get(str(country).strip().upper())
    if not code:
        raise ValueError("Choose India (+91) or Nepal (+977).")

    digits = re.sub(r"\D", "", str(national or ""))
    if digits.startswith(code) and len(digits) == len(code) + 10:
        digits = digits[len(code):]

    if len(digits) != 10:
        raise ValueError("Mobile number must contain exactly 10 national digits.")

    return code + digits
