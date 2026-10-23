import datetime

from app.ist_time import ist_date_to_utc_range, ist_today, ist_wall_clock_to_utc, to_ist


def test_to_ist_adds_offset():
    utc_dt = datetime.datetime(2026, 7, 16, 18, 30, 0)
    assert to_ist(utc_dt) == datetime.datetime(2026, 7, 17, 0, 0, 0)


def test_ist_today_crosses_utc_midnight_boundary():
    # 2026-07-16 20:00 UTC is 2026-07-17 01:30 IST — a different calendar day.
    utc_now = datetime.datetime(2026, 7, 16, 20, 0, 0)
    assert ist_today(utc_now) == datetime.date(2026, 7, 17)


def test_ist_today_matches_utc_when_well_within_the_day():
    utc_now = datetime.datetime(2026, 7, 16, 10, 0, 0)
    assert ist_today(utc_now) == datetime.date(2026, 7, 16)


def test_ist_date_to_utc_range_spans_correct_utc_window():
    ist_date = datetime.date(2026, 7, 17)
    start, end = ist_date_to_utc_range(ist_date)
    # IST day 2026-07-17 00:00 -> UTC 2026-07-16 18:30
    assert start == datetime.datetime(2026, 7, 16, 18, 30, 0)
    # IST day 2026-07-17 23:59:59.999999 -> UTC 2026-07-17 18:29:59.999999
    assert end == datetime.datetime(2026, 7, 17, 18, 29, 59, 999999)


def test_ist_wall_clock_to_utc_converts_correctly():
    # 23:45 IST on 2026-07-17 is 18:15 UTC on 2026-07-17
    result = ist_wall_clock_to_utc(datetime.date(2026, 7, 17), 23, 45)
    assert result == datetime.datetime(2026, 7, 17, 18, 15, 0)


def test_ist_wall_clock_to_utc_crosses_to_previous_utc_day():
    # 02:00 IST on 2026-07-17 is 20:30 UTC on 2026-07-16
    result = ist_wall_clock_to_utc(datetime.date(2026, 7, 17), 2, 0)
    assert result == datetime.datetime(2026, 7, 16, 20, 30, 0)
