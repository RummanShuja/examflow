"""Small representation helpers shared by independent scheduling and validation."""
from datetime import datetime, timedelta
import hashlib
import json

OFFSET = "+05:30"
HORIZON_START = "2026-11-16T00:00:00+05:30"
HORIZON_END = "2026-11-28T00:00:00+05:30"
ORIGIN = "2026-07-01T00:00:00+05:30"
APPROVAL_DATE = "2026-10-01T00:00:00+05:30"
CAPACITY_CHANGE = "2026-11-23T00:00:00+05:30"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def dt(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() != timedelta(hours=5, minutes=30):
        raise ValueError("Timestamp must use the declared +05:30 offset")
    return result


def plus(value, minutes):
    return (dt(value) + timedelta(minutes=minutes)).isoformat(timespec="seconds")


def minutes(start, end):
    return int((dt(end) - dt(start)).total_seconds() // 60)


def overlaps(a, b, c, d):
    return a < d and c < b


def covered(intervals, start, end):
    """Union coverage permits adjacent availability records without a gap."""
    cursor = start
    for left, right in sorted(intervals):
        if right <= cursor:
            continue
        if left > cursor:
            return False
        cursor = max(cursor, right)
        if cursor >= end:
            return True
    return False


def days():
    day = dt(HORIZON_START)
    while day.isoformat(timespec="seconds") < HORIZON_END:
        if day.weekday() < 5:
            yield day.date().isoformat()
        day += timedelta(days=1)


def at(day, hour, minute=0):
    return f"{day}T{hour:02d}:{minute:02d}:00{OFFSET}"


def rows(conn, table):
    # Table names only come from our schema metadata / literal constants.
    return [dict(row) for row in conn.execute(f'SELECT * FROM "{table}"')]
