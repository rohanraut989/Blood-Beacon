import pytest

from phone import normalize_phone


def test_india_happy_path():
    assert normalize_phone("91", "98765 43210") == "919876543210"


def test_nepal_happy_path():
    assert normalize_phone("977", "9817612738") == "9779817612738"


def test_pasted_country_code_is_not_duplicated():
    assert normalize_phone("91", "+91 98765 43210") == "919876543210"


def test_too_short_number_is_rejected():
    with pytest.raises(ValueError, match="exactly 10"):
        normalize_phone("91", "987654321")
