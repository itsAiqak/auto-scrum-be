"""The database keeps naive UTC; the app speaks the team's local time ('YYYY-MM-DDTHH:mm', 'YYYY-MM-DD')."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo


def to_db(value: datetime, tz: ZoneInfo) -> datetime:
    """Naive UTC for storage. A naive input is taken as team-local time."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=tz)
    return value.astimezone(UTC).replace(tzinfo=None)


def local_minute(stored: datetime, tz: ZoneInfo) -> str:
    """Stored naive UTC -> 'YYYY-MM-DDTHH:mm' in the team's time zone, as the app's Commit.timestamp."""
    return stored.replace(tzinfo=UTC).astimezone(tz).strftime("%Y-%m-%dT%H:%M")


def day_start(day: date, tz: ZoneInfo) -> datetime:
    """Team-local midnight of `day`, as stored naive UTC."""
    return to_db(datetime.combine(day, time.min, tzinfo=tz), tz)


def now_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
