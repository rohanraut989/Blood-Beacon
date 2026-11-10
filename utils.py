from datetime import date, datetime


def parse_date(value):
    """Return a date from date/datetime objects or ISO date/timestamp strings."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            return date.fromisoformat(normalized[:10])
    raise TypeError(f"Unsupported date value: {type(value).__name__}")
