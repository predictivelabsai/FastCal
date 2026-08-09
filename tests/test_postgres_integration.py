from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.getenv("FASTCAL_RUN_DB_TESTS") != "1",
    reason="set FASTCAL_RUN_DB_TESTS=1 with the isolated FastCal PostgreSQL schema",
)


def test_round_robin_booking_is_transactional():
    from fastcal.db.base import SessionLocal
    from fastcal.db.models import (
        AvailabilityRule,
        BookingHost,
        EventType,
        EventTypeHost,
        Membership,
        Organisation,
        Schedule,
        User,
    )
    from fastcal.services.scheduling import available_slots, create_booking

    marker = uuid.uuid4().hex[:10]
    db = SessionLocal()
    try:
        organisation = Organisation(
            id=f"test:{marker}", name="Test workspace", slug=f"test-{marker}"
        )
        alice = User(
            id=f"alice:{marker}", email=f"alice-{marker}@example.com", name="Alice"
        )
        bob = User(id=f"bob:{marker}", email=f"bob-{marker}@example.com", name="Bob")
        db.add_all([organisation, alice, bob])
        db.flush()
        db.add_all(
            [
                Membership(
                    organisation_id=organisation.id, user_id=alice.id, role="owner"
                ),
                Membership(
                    organisation_id=organisation.id, user_id=bob.id, role="member"
                ),
            ]
        )
        schedules = []
        for user in (alice, bob):
            schedule = Schedule(
                organisation_id=organisation.id,
                user_id=user.id,
                name=f"Default {user.name}",
                timezone="Europe/Tallinn",
                is_default=True,
            )
            db.add(schedule)
            db.flush()
            db.add(
                AvailabilityRule(
                    schedule_id=schedule.id,
                    weekday=0,
                    start_time=time(9),
                    end_time=time(11),
                )
            )
            schedules.append(schedule)
        event_type = EventType(
            organisation_id=organisation.id,
            owner_id=alice.id,
            schedule_id=schedules[0].id,
            title="Round robin introduction",
            slug="round-robin",
            duration_minutes=30,
            slot_interval_minutes=30,
            scheduling_type="round_robin",
            timezone="Europe/Tallinn",
            minimum_notice_minutes=0,
        )
        db.add(event_type)
        db.flush()
        db.add_all(
            [
                EventTypeHost(
                    event_type_id=event_type.id,
                    user_id=alice.id,
                    schedule_id=schedules[0].id,
                ),
                EventTypeHost(
                    event_type_id=event_type.id,
                    user_id=bob.id,
                    schedule_id=schedules[1].id,
                ),
            ]
        )
        db.flush()
        now = datetime(2026, 8, 9, 6, tzinfo=UTC)
        slots = available_slots(
            db,
            event_type,
            now,
            now + timedelta(days=2),
            include_external=False,
            now=now,
        )
        assert slots
        created = create_booking(
            db,
            event_type=event_type,
            starts_at=slots[0].starts_at,
            ends_at=slots[0].ends_at,
            guest_name="Guest",
            guest_email="guest@example.com",
            guest_timezone="Europe/Tallinn",
            include_external=False,
            now=now,
        )
        hosts = db.scalars(
            select(BookingHost).where(BookingHost.booking_id == created.booking.id)
        ).all()
        assert len(hosts) == 1
        assert hosts[0].user_id in {alice.id, bob.id}
    finally:
        db.rollback()
        db.close()
