"""Timezone-safe availability and interval operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Window:
    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True)
class Rule:
    weekday: int
    start_time: time
    end_time: time


@dataclass(frozen=True)
class Override:
    date: date
    available: bool
    start_time: time | None = None
    end_time: time | None = None


def round_robin_order(
    candidates: list[tuple[str, int, int, int, datetime | None]],
) -> list[str]:
    """Rank hosts by priority, weighted assignment share, and oldest assignment."""
    if not candidates:
        return []
    highest_priority = max(priority for _, priority, _, _, _ in candidates)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    eligible = [item for item in candidates if item[1] == highest_priority]
    return [
        user_id
        for user_id, _priority, _weight, _count, _last in sorted(
            eligible,
            key=lambda item: (
                item[3] / max(1, item[2]),
                item[4] or epoch,
                item[0],
            ),
        )
    ]


def overlaps(left: Window, right: Window) -> bool:
    return left.starts_at < right.ends_at and left.ends_at > right.starts_at


def local_windows(
    day: date,
    timezone: str,
    rules: list[Rule],
    overrides: list[Override],
) -> list[Window]:
    tz = ZoneInfo(timezone)
    day_overrides = [item for item in overrides if item.date == day]
    if day_overrides:
        return [
            Window(
                datetime.combine(day, item.start_time, tz),
                datetime.combine(day, item.end_time, tz),
            )
            for item in day_overrides
            if item.available
            and item.start_time
            and item.end_time
            and item.end_time > item.start_time
        ]
    return [
        Window(
            datetime.combine(day, rule.start_time, tz),
            datetime.combine(day, rule.end_time, tz),
        )
        for rule in rules
        if rule.weekday == day.weekday() and rule.end_time > rule.start_time
    ]


def candidate_slots(
    *,
    timezone: str,
    rules: list[Rule],
    overrides: list[Override],
    duration_minutes: int,
    interval_minutes: int,
    range_start: datetime,
    range_end: datetime,
    minimum_notice_minutes: int,
    now: datetime | None = None,
) -> list[Window]:
    tz = ZoneInfo(timezone)
    now = (now or datetime.now(UTC)).astimezone(tz)
    earliest = now + timedelta(minutes=minimum_notice_minutes)
    cursor = max(range_start.astimezone(tz).date(), now.date())
    final_day = range_end.astimezone(tz).date()
    duration = timedelta(minutes=duration_minutes)
    interval = timedelta(minutes=max(1, interval_minutes))
    slots: list[Window] = []
    while cursor <= final_day:
        for window in local_windows(cursor, timezone, rules, overrides):
            start = window.starts_at
            while start + duration <= window.ends_at:
                end = start + duration
                if (
                    start >= earliest
                    and start >= range_start.astimezone(tz)
                    and end <= range_end.astimezone(tz)
                ):
                    slots.append(Window(start, end))
                start += interval
        cursor += timedelta(days=1)
    return slots


def remove_conflicts(
    slots: list[Window],
    busy: list[Window],
    before_buffer_minutes: int,
    after_buffer_minutes: int,
) -> list[Window]:
    before = timedelta(minutes=before_buffer_minutes)
    after = timedelta(minutes=after_buffer_minutes)
    expanded = [Window(item.starts_at - after, item.ends_at + before) for item in busy]
    return [
        slot for slot in slots if not any(overlaps(slot, item) for item in expanded)
    ]
