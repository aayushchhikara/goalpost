from datetime import UTC, date, datetime

import pytest
from goalpost.services.dates import decode_days, encode_days, local_date, week_monday

IST = "Asia/Kolkata"


@pytest.mark.parametrize(
    ("day", "monday"),
    [
        (date(2026, 10, 26), date(2026, 10, 26)),  # Monday is its own week start
        (date(2026, 10, 28), date(2026, 10, 26)),  # Wednesday
        (date(2026, 11, 1), date(2026, 10, 26)),  # Sunday closes week 44
    ],
)
def test_week_monday(day: date, monday: date) -> None:
    assert week_monday(day) == monday


def test_submission_at_1150pm_ist_counts_for_that_day() -> None:
    # 23:50 IST on Mon 26 Oct is 18:20 UTC; synced at 3 am, it still counts for the 26th.
    assert local_date(datetime(2026, 10, 26, 18, 20, tzinfo=UTC), IST) == date(2026, 10, 26)
    # Eleven minutes later it is 00:01 IST on the 27th.
    assert local_date(datetime(2026, 10, 26, 18, 31, tzinfo=UTC), IST) == date(2026, 10, 27)


def test_sunday_to_monday_boundary() -> None:
    # Sun 25 Oct 23:50 IST belongs to the week of Mon 19 Oct.
    sunday_night = local_date(datetime(2026, 10, 25, 18, 20, tzinfo=UTC), IST)
    assert sunday_night == date(2026, 10, 25)
    assert week_monday(sunday_night) == date(2026, 10, 19)

    # Mon 26 Oct 00:10 IST is still Sunday in UTC, but starts the new week.
    monday_morning = local_date(datetime(2026, 10, 25, 18, 40, tzinfo=UTC), IST)
    assert monday_morning == date(2026, 10, 26)
    assert week_monday(monday_morning) == date(2026, 10, 26)


def test_local_date_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="naive"):
        local_date(datetime(2026, 10, 26, 18, 20), IST)


def test_local_date_accepts_zoneinfo() -> None:
    from zoneinfo import ZoneInfo

    ts = datetime(2026, 10, 25, 18, 40, tzinfo=UTC)
    assert local_date(ts, ZoneInfo(IST)) == local_date(ts, IST)


def test_recurrence_mask_round_trip() -> None:
    mon_to_thu_and_sat = [0, 1, 2, 3, 5]
    assert encode_days(mon_to_thu_and_sat) == 0b0101111 == 47
    assert decode_days(47) == mon_to_thu_and_sat
    assert decode_days(encode_days([6, 0, 0])) == [0, 6]  # order and duplicates don't matter
    assert encode_days([]) == 0
    assert decode_days(0) == []
    assert decode_days(127) == list(range(7))


@pytest.mark.parametrize("day", [-1, 7])
def test_encode_days_rejects_invalid_weekday(day: int) -> None:
    with pytest.raises(ValueError):
        encode_days([day])


@pytest.mark.parametrize("mask", [-1, 128])
def test_decode_days_rejects_invalid_mask(mask: int) -> None:
    with pytest.raises(ValueError):
        decode_days(mask)
