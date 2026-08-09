"""Availability, host assignment, and booking lifecycle orchestration."""

from __future__ import annotations

import hashlib
import secrets
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from fastcal.db.models import (
    AvailabilityRule,
    Booking,
    BookingAudit,
    BookingHost,
    BusyPeriod,
    DateOverride,
    EventType,
    EventTypeHost,
    OutboxEvent,
    Schedule,
    User,
)
from fastcal.domain.slots import (
    Override,
    Rule,
    Window,
    candidate_slots,
    remove_conflicts,
    round_robin_order,
)
from fastcal.providers.google_calendar import busy_for_users

ACTIVE_BOOKING_STATUSES = ("accepted", "pending")


@dataclass(frozen=True)
class Slot:
    starts_at: datetime
    ends_at: datetime
    host_ids: tuple[str, ...]


@dataclass(frozen=True)
class CreatedBooking:
    booking: Booking
    cancel_token: str
    reschedule_token: str


def _hosts(db: Session, event_type: EventType) -> list[EventTypeHost]:
    configured = db.scalars(
        select(EventTypeHost).where(
            EventTypeHost.event_type_id == event_type.id,
            EventTypeHost.active.is_(True),
        )
    ).all()
    if configured:
        return list(configured)
    return [
        EventTypeHost(
            event_type_id=event_type.id,
            user_id=event_type.owner_id,
            schedule_id=event_type.schedule_id,
            priority=0,
            weight=100,
            active=True,
        )
    ]


def _schedule(
    db: Session, host: EventTypeHost, event_type: EventType
) -> Schedule | None:
    schedule_id = host.schedule_id or event_type.schedule_id
    if schedule_id:
        return db.get(Schedule, schedule_id)
    return db.scalar(
        select(Schedule).where(
            Schedule.user_id == host.user_id,
            Schedule.is_default.is_(True),
        )
    )


def _internal_busy(
    db: Session,
    user_ids: list[str],
    starts_at: datetime,
    ends_at: datetime,
) -> dict[str, list[Window]]:
    result: dict[str, list[Window]] = defaultdict(list)
    rows = db.execute(
        select(BookingHost.user_id, Booking.starts_at, Booking.ends_at)
        .join(Booking, Booking.id == BookingHost.booking_id)
        .where(
            BookingHost.user_id.in_(user_ids),
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            Booking.starts_at < ends_at,
            Booking.ends_at > starts_at,
        )
    ).all()
    for user_id, start, end in rows:
        result[user_id].append(Window(start, end))
    cached = db.scalars(
        select(BusyPeriod).where(
            BusyPeriod.user_id.in_(user_ids),
            BusyPeriod.status == "busy",
            BusyPeriod.starts_at < ends_at,
            BusyPeriod.ends_at > starts_at,
        )
    ).all()
    for item in cached:
        result[item.user_id].append(Window(item.starts_at, item.ends_at))
    return result


def available_slots(
    db: Session,
    event_type: EventType,
    range_start: datetime,
    range_end: datetime,
    *,
    include_external: bool = True,
    now: datetime | None = None,
) -> list[Slot]:
    hosts = _hosts(db, event_type)
    host_ids = [host.user_id for host in hosts]
    internal = _internal_busy(db, host_ids, range_start, range_end)
    external_raw = (
        busy_for_users(db, host_ids, range_start, range_end) if include_external else {}
    )
    external = {
        user_id: [Window(start, end) for start, end in periods]
        for user_id, periods in external_raw.items()
    }
    by_host: dict[str, list[Window]] = {}
    for host in hosts:
        schedule = _schedule(db, host, event_type)
        if schedule is None:
            by_host[host.user_id] = []
            continue
        rules = [
            Rule(row.weekday, row.start_time, row.end_time)
            for row in db.scalars(
                select(AvailabilityRule).where(
                    AvailabilityRule.schedule_id == schedule.id
                )
            ).all()
        ]
        overrides = [
            Override(row.date, row.available, row.start_time, row.end_time)
            for row in db.scalars(
                select(DateOverride).where(
                    DateOverride.schedule_id == schedule.id,
                    DateOverride.date >= range_start.date(),
                    DateOverride.date <= range_end.date(),
                )
            ).all()
        ]
        candidates = candidate_slots(
            timezone=schedule.timezone or event_type.timezone,
            rules=rules,
            overrides=overrides,
            duration_minutes=event_type.duration_minutes,
            interval_minutes=event_type.slot_interval_minutes
            or event_type.duration_minutes,
            range_start=range_start,
            range_end=range_end,
            minimum_notice_minutes=event_type.minimum_notice_minutes,
            now=now,
        )
        by_host[host.user_id] = remove_conflicts(
            candidates,
            internal.get(host.user_id, []) + external.get(host.user_id, []),
            event_type.before_buffer_minutes,
            event_type.after_buffer_minutes,
        )

    keyed: dict[tuple[datetime, datetime], set[str]] = defaultdict(set)
    for user_id, windows in by_host.items():
        for window in windows:
            keyed[
                (window.starts_at.astimezone(UTC), window.ends_at.astimezone(UTC))
            ].add(user_id)
    expected = set(host_ids)
    slots: list[Slot] = []
    for (start, end), eligible in sorted(keyed.items()):
        if event_type.scheduling_type == "collective" and eligible != expected:
            continue
        if (
            event_type.scheduling_type == "individual"
            and event_type.owner_id not in eligible
        ):
            continue
        slot_hosts = (
            expected if event_type.scheduling_type == "collective" else eligible
        )
        slots.append(Slot(start, end, tuple(sorted(slot_hosts))))
    return slots


def choose_round_robin_host(
    db: Session,
    event_type: EventType,
    eligible_host_ids: tuple[str, ...],
) -> str:
    hosts = [
        host for host in _hosts(db, event_type) if host.user_id in eligible_host_ids
    ]
    if not hosts:
        raise ValueError("No host is available for this slot")
    highest_priority = max(host.priority for host in hosts)
    hosts = [host for host in hosts if host.priority == highest_priority]
    counts = dict(
        db.execute(
            select(BookingHost.user_id, func.count(BookingHost.id))
            .join(Booking, Booking.id == BookingHost.booking_id)
            .where(
                Booking.event_type_id == event_type.id,
                BookingHost.user_id.in_([host.user_id for host in hosts]),
                Booking.status.in_(ACTIVE_BOOKING_STATUSES),
            )
            .group_by(BookingHost.user_id)
        ).all()
    )
    latest = dict(
        db.execute(
            select(BookingHost.user_id, func.max(Booking.created_at))
            .join(Booking, Booking.id == BookingHost.booking_id)
            .where(
                Booking.event_type_id == event_type.id,
                BookingHost.user_id.in_([host.user_id for host in hosts]),
            )
            .group_by(BookingHost.user_id)
        ).all()
    )
    ranked = round_robin_order(
        [
            (
                host.user_id,
                host.priority,
                host.weight,
                counts.get(host.user_id, 0),
                latest.get(host.user_id),
            )
            for host in hosts
        ]
    )
    return ranked[0]


def create_booking(
    db: Session,
    *,
    event_type: EventType,
    starts_at: datetime,
    ends_at: datetime,
    guest_name: str,
    guest_email: str,
    guest_timezone: str,
    responses: dict[str, Any] | None = None,
    attendees: list[dict[str, Any]] | None = None,
    idempotency_key: str | None = None,
    include_external: bool = True,
    now: datetime | None = None,
) -> CreatedBooking:
    if "@" not in guest_email or not guest_name.strip():
        raise ValueError("A valid guest name and email are required")
    if (
        ends_at <= starts_at
        or int((ends_at - starts_at).total_seconds() // 60)
        != event_type.duration_minutes
    ):
        raise ValueError("The requested interval does not match the event duration")
    if idempotency_key:
        existing = db.scalar(
            select(Booking).where(
                Booking.organisation_id == event_type.organisation_id,
                Booking.idempotency_key == idempotency_key,
            )
        )
        if existing:
            raise ValueError(
                f"A booking already exists for idempotency key {idempotency_key}"
            )

    if db.bind and db.bind.dialect.name == "postgresql":
        lock_key = f"{event_type.id}:{starts_at.astimezone(UTC).isoformat()}"
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": lock_key}
        )
    locked = db.scalar(
        select(EventType).where(EventType.id == event_type.id).with_for_update()
    )
    if locked is None or not locked.active:
        raise ValueError("This event type is unavailable")
    candidates = available_slots(
        db,
        locked,
        starts_at - timedelta(minutes=1),
        ends_at + timedelta(minutes=1),
        include_external=include_external,
        now=now,
    )
    selected = next(
        (
            slot
            for slot in candidates
            if slot.starts_at == starts_at.astimezone(UTC)
            and slot.ends_at == ends_at.astimezone(UTC)
        ),
        None,
    )
    if selected is None:
        raise ValueError("That slot is no longer available")
    if locked.scheduling_type == "round_robin":
        host_ids = (choose_round_robin_host(db, locked, selected.host_ids),)
    elif locked.scheduling_type == "collective":
        host_ids = selected.host_ids
    else:
        host_ids = (locked.owner_id,)

    cancel_token = secrets.token_urlsafe(32)
    reschedule_token = secrets.token_urlsafe(32)
    status = "pending" if locked.requires_confirmation else "accepted"
    booking = Booking(
        organisation_id=locked.organisation_id,
        event_type_id=locked.id,
        primary_host_id=host_ids[0],
        title=locked.title,
        guest_name=guest_name.strip()[:160],
        guest_email=guest_email.strip().lower()[:320],
        guest_timezone=guest_timezone,
        starts_at=starts_at.astimezone(UTC),
        ends_at=ends_at.astimezone(UTC),
        status=status,
        location=locked.location_value,
        responses=responses or {},
        attendees=attendees or [],
        idempotency_key=idempotency_key,
        cancel_token_hash=hashlib.sha256(cancel_token.encode()).hexdigest(),
        reschedule_token_hash=hashlib.sha256(reschedule_token.encode()).hexdigest(),
    )
    db.add(booking)
    db.flush()
    for user_id in host_ids:
        db.add(
            BookingHost(
                booking_id=booking.id,
                user_id=user_id,
                assignment_type=locked.scheduling_type,
            )
        )
    db.add(
        BookingAudit(
            booking_id=booking.id,
            action="created",
            actor_type="booker",
            actor_id=booking.guest_email,
            details={"status": status, "hosts": list(host_ids)},
        )
    )
    db.add(
        OutboxEvent(
            organisation_id=booking.organisation_id,
            topic="booking.created",
            aggregate_id=booking.id,
            payload={"booking_id": booking.id},
        )
    )
    db.flush()
    return CreatedBooking(booking, cancel_token, reschedule_token)


def cancel_booking(db: Session, token: str, reason: str = "") -> Booking | None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    booking = db.scalar(
        select(Booking)
        .where(
            Booking.cancel_token_hash == digest,
            Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        )
        .with_for_update()
    )
    if booking is None:
        return None
    booking.status = "cancelled"
    booking.cancelled_at = datetime.now(UTC)
    booking.cancellation_reason = reason.strip()[:2000]
    db.add(
        BookingAudit(
            booking_id=booking.id,
            action="cancelled",
            actor_type="booker",
            actor_id=booking.guest_email,
            details={"reason": booking.cancellation_reason},
        )
    )
    db.add(
        OutboxEvent(
            organisation_id=booking.organisation_id,
            topic="booking.cancelled",
            aggregate_id=booking.id,
            payload={"booking_id": booking.id},
        )
    )
    return booking


def booking_hosts(db: Session, booking_id: str) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(BookingHost, BookingHost.user_id == User.id)
            .where(BookingHost.booking_id == booking_id)
        ).all()
    )
