"""Resolve configured event-analysis slots in Beijing time."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")
DEFAULT_SCHEDULE = ",".join(
    f"{hour:02d}:00" for hour in range(24)
)


def parse_schedule(value=DEFAULT_SCHEDULE):
    slots = []
    for part in value.split(","):
        if not re.fullmatch(r"\d{2}:\d{2}", part.strip()):
            raise ValueError("Analysis schedule must contain HH:MM times.")
        hour, minute = map(int, part.strip().split(":"))
        if hour > 23 or minute > 59 or (hour, minute) in slots:
            raise ValueError("Invalid or duplicate analysis schedule time.")
        slots.append((hour, minute))
    return tuple(sorted(slots))


def _slot_at(day, hour, minute):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=BEIJING)


def due_slot(now, schedule=DEFAULT_SCHEDULE):
    """Return the latest configured Beijing slot that has already started.

    The slot stays due after its clock minute, so a beat that wakes late
    still opens that cutoff. Messages ingested after the slot wait for the
    next one. A naive datetime is rejected so the host timezone cannot move
    the cutoff.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(
            "Analysis schedule requires a timezone-aware datetime."
        )
    local = now.astimezone(BEIJING)
    times = parse_schedule(schedule)
    started = []
    for day_offset in (0, -1):
        day = local.date() + timedelta(days=day_offset)
        for hour, minute in times:
            slot = _slot_at(day, hour, minute)
            if slot <= local:
                started.append(slot)
    if not started:
        return None
    return max(started).isoformat(timespec="minutes")


def slot_boundary(slot):
    boundary = datetime.fromisoformat(slot)
    if boundary.tzinfo is None:
        raise ValueError("Analysis slot is missing a timezone.")
    return boundary
