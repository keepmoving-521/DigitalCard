from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return a timezone-naive UTC value for consistent database storage."""
    return datetime.now(UTC).replace(tzinfo=None)
