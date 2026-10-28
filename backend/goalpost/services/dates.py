"""Day, week and recurrence helpers. Every date decision goes through these.

Weeks run Monday to Sunday and days run midnight to midnight in the user's timezone.
"""

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ALL_DAYS_MASK = 0b1111111


def week_monday(d: date) -> date:
    """The Monday of the week containing `d`."""
    return d - timedelta(days=d.weekday())


def local_date(utc_ts: datetime, tz: str | ZoneInfo) -> date:
    """The calendar day `utc_ts` falls on in timezone `tz`."""
    if utc_ts.tzinfo is None:
        raise ValueError("naive datetime; pass a timezone-aware (UTC) timestamp")
    zone = tz if isinstance(tz, ZoneInfo) else ZoneInfo(tz)
    return utc_ts.astimezone(zone).date()


def encode_days(days: Iterable[int]) -> int:
    """Encode weekdays (Monday = 0 … Sunday = 6, as `date.weekday()`) into a bitmask."""
    mask = 0
    for day in days:
        if not 0 <= day <= 6:
            raise ValueError(f"weekday must be 0 (Monday) to 6 (Sunday), got {day}")
        mask |= 1 << day
    return mask


def decode_days(mask: int) -> list[int]:
    """Decode a bitmask into sorted weekdays (Monday = 0 … Sunday = 6)."""
    if not 0 <= mask <= ALL_DAYS_MASK:
        raise ValueError(f"recurrence mask must be 0 to {ALL_DAYS_MASK}, got {mask}")
    return [day for day in range(7) if mask & (1 << day)]
