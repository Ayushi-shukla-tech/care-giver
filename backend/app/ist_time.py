import datetime

IST_OFFSET = datetime.timedelta(hours=5, minutes=30)


def to_ist(utc_dt: datetime.datetime) -> datetime.datetime:
    return utc_dt + IST_OFFSET


def ist_today(utc_now: datetime.datetime) -> datetime.date:
    return to_ist(utc_now).date()


def ist_date_to_utc_range(ist_date: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    ist_start = datetime.datetime.combine(ist_date, datetime.time.min)
    ist_end = datetime.datetime.combine(ist_date, datetime.time.max)
    return ist_start - IST_OFFSET, ist_end - IST_OFFSET


def ist_wall_clock_to_utc(ist_date: datetime.date, hour: int, minute: int) -> datetime.datetime:
    ist_dt = datetime.datetime.combine(ist_date, datetime.time(hour, minute))
    return ist_dt - IST_OFFSET
