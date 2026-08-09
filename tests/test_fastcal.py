from __future__ import annotations

from datetime import UTC, date, datetime, time

from starlette.testclient import TestClient

from fastcal.domain.slots import (
    Override,
    Rule,
    Window,
    candidate_slots,
    remove_conflicts,
    round_robin_order,
)


def test_public_landing_health_and_api_contract():
    from app import app

    client = TestClient(app)
    assert "Make time work for everyone" in client.get("/").text
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/v1/health").json()["product"] == "FastCal"
    paths = client.get("/api/openapi.json").json()["paths"]
    assert "/v1/event-types/{organisation_slug}/{event_type_slug}/slots" in paths
    assert "/v1/bookings" in paths


def test_weekly_slots_are_timezone_and_dst_safe():
    slots = candidate_slots(
        timezone="Europe/Tallinn",
        rules=[Rule(0, time(9), time(11))],
        overrides=[],
        duration_minutes=30,
        interval_minutes=30,
        range_start=datetime(2026, 10, 25, tzinfo=UTC),
        range_end=datetime(2026, 10, 27, tzinfo=UTC),
        minimum_notice_minutes=0,
        now=datetime(2026, 10, 24, tzinfo=UTC),
    )
    assert len(slots) == 4
    assert slots[0].starts_at.utcoffset().total_seconds() == 2 * 3600
    assert slots[0].starts_at.hour == 9


def test_date_override_replaces_weekly_rule():
    monday = date(2026, 8, 10)
    slots = candidate_slots(
        timezone="Europe/Tallinn",
        rules=[Rule(0, time(9), time(17))],
        overrides=[Override(monday, True, time(13), time(14))],
        duration_minutes=30,
        interval_minutes=30,
        range_start=datetime(2026, 8, 9, tzinfo=UTC),
        range_end=datetime(2026, 8, 11, tzinfo=UTC),
        minimum_notice_minutes=0,
        now=datetime(2026, 8, 8, tzinfo=UTC),
    )
    assert [slot.starts_at.hour for slot in slots] == [13, 13]
    assert [slot.starts_at.minute for slot in slots] == [0, 30]


def test_conflict_buffers_remove_adjacent_slot():
    slots = [
        Window(
            datetime(2026, 8, 10, 8, tzinfo=UTC),
            datetime(2026, 8, 10, 8, 30, tzinfo=UTC),
        ),
        Window(
            datetime(2026, 8, 10, 8, 30, tzinfo=UTC),
            datetime(2026, 8, 10, 9, tzinfo=UTC),
        ),
    ]
    busy = [
        Window(
            datetime(2026, 8, 10, 9, tzinfo=UTC),
            datetime(2026, 8, 10, 9, 30, tzinfo=UTC),
        )
    ]
    remaining = remove_conflicts(
        slots, busy, before_buffer_minutes=0, after_buffer_minutes=15
    )
    assert remaining == [slots[0]]


def test_round_robin_prefers_priority_then_weighted_share_then_oldest():
    recent = datetime(2026, 8, 9, tzinfo=UTC)
    old = datetime(2026, 8, 1, tzinfo=UTC)
    candidates = [
        ("low-priority", 0, 100, 0, None),
        ("alice", 10, 100, 2, recent),
        ("bob", 10, 200, 2, recent),
        ("carol", 10, 100, 1, old),
    ]
    assert round_robin_order(candidates) == ["carol", "bob", "alice"]
