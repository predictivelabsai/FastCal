"""Tenant-scoped scheduling models."""

from __future__ import annotations

import secrets
import uuid
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from fastcal.config import settings

from .base import Base

SCHEMA = settings.DB_SCHEMA


def new_id() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Organisation(Base, TimestampMixin):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Tallinn")
    locale: Mapped[str] = mapped_column(String(16), default="en")
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    fastoffice_subject: Mapped[str | None] = mapped_column(String(255), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organisation_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.organisations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(24), default="member")
    accepted: Mapped[bool] = mapped_column(Boolean, default=True)


class Team(Base, TimestampMixin):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("organisation_id", "slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.organisations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80))


class TeamMember(Base, TimestampMixin):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    team_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.teams.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(24), default="member")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class OAuthCredential(Base, TimestampMixin):
    __tablename__ = "oauth_credentials"
    __table_args__ = (UniqueConstraint("user_id", "provider", "provider_account_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(40))
    provider_account_id: Mapped[str] = mapped_column(String(255), default="primary")
    encrypted_access_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    encrypted_refresh_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str] = mapped_column(Text, default="")
    invalid: Mapped[bool] = mapped_column(Boolean, default=False)


class CalendarConnection(Base, TimestampMixin):
    __tablename__ = "calendar_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider", "external_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    credential_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.oauth_credentials.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(160), default="Calendar")
    selected_for_conflicts: Mapped[bool] = mapped_column(Boolean, default=True)
    destination: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_token: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Schedule(Base, TimestampMixin):
    __tablename__ = "schedules"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.organisations.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(120), default="Working hours")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Tallinn")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class AvailabilityRule(Base, TimestampMixin):
    __tablename__ = "availability_rules"
    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6"),
        CheckConstraint("end_time > start_time"),
        Index("availability_schedule_day", "schedule_id", "weekday"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    schedule_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.schedules.id", ondelete="CASCADE")
    )
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class DateOverride(Base, TimestampMixin):
    __tablename__ = "date_overrides"
    __table_args__ = (
        UniqueConstraint("schedule_id", "date", "start_time", "end_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    schedule_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.schedules.id", ondelete="CASCADE")
    )
    date: Mapped[date] = mapped_column(Date)
    available: Mapped[bool] = mapped_column(Boolean, default=False)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)


class EventType(Base, TimestampMixin):
    __tablename__ = "event_types"
    __table_args__ = (
        UniqueConstraint("organisation_id", "slug"),
        CheckConstraint("duration_minutes > 0"),
        CheckConstraint("scheduling_type IN ('individual','collective','round_robin')"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.organisations.id", ondelete="CASCADE")
    )
    owner_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    team_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.teams.id", ondelete="CASCADE")
    )
    schedule_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.schedules.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    slot_interval_minutes: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Tallinn")
    scheduling_type: Mapped[str] = mapped_column(String(24), default="individual")
    minimum_notice_minutes: Mapped[int] = mapped_column(Integer, default=240)
    before_buffer_minutes: Mapped[int] = mapped_column(Integer, default=0)
    after_buffer_minutes: Mapped[int] = mapped_column(Integer, default=10)
    future_limit_days: Mapped[int] = mapped_column(Integer, default=60)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_guests: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    location_type: Mapped[str] = mapped_column(String(32), default="fastmeet")
    location_value: Mapped[str] = mapped_column(String(500), default="")
    booking_fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    success_redirect_url: Mapped[str | None] = mapped_column(String(1000))


class EventTypeHost(Base, TimestampMixin):
    __tablename__ = "event_type_hosts"
    __table_args__ = (
        UniqueConstraint("event_type_id", "user_id"),
        CheckConstraint("weight > 0"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.event_types.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    schedule_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.schedules.id", ondelete="SET NULL")
    )
    priority: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[int] = mapped_column(Integer, default=100)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class BusyPeriod(Base, TimestampMixin):
    __tablename__ = "busy_periods"
    __table_args__ = (Index("busy_user_time", "user_id", "starts_at", "ends_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE")
    )
    calendar_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.calendar_connections.id", ondelete="CASCADE")
    )
    external_id: Mapped[str] = mapped_column(String(500))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="busy")


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("organisation_id", "idempotency_key"),
        Index("booking_event_time", "event_type_id", "starts_at", "ends_at", "status"),
        Index("booking_org_time", "organisation_id", "starts_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    uid: Mapped[str] = mapped_column(
        String(48), unique=True, default=lambda: secrets.token_urlsafe(18)
    )
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.organisations.id", ondelete="CASCADE")
    )
    event_type_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.event_types.id", ondelete="RESTRICT")
    )
    primary_host_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(240))
    guest_name: Mapped[str] = mapped_column(String(160))
    guest_email: Mapped[str] = mapped_column(String(320), index=True)
    guest_timezone: Mapped[str] = mapped_column(String(64))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="accepted")
    location: Mapped[str] = mapped_column(String(500), default="")
    meet_url: Mapped[str] = mapped_column(String(1000), default="")
    responses: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attendees: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    idempotency_key: Mapped[str | None] = mapped_column(String(160))
    cancel_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    reschedule_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    rescheduled_from_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.bookings.id", ondelete="SET NULL")
    )
    external_calendar_event_id: Mapped[str | None] = mapped_column(String(500))
    fastmeet_meeting_id: Mapped[str | None] = mapped_column(String(120))


class BookingHost(Base, TimestampMixin):
    __tablename__ = "booking_hosts"
    __table_args__ = (UniqueConstraint("booking_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.bookings.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="RESTRICT")
    )
    assignment_type: Mapped[str] = mapped_column(String(24), default="host")


class BookingAudit(Base):
    __tablename__ = "booking_audit"
    __table_args__ = (Index("booking_audit_booking_time", "booking_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.bookings.id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(40))
    actor_type: Mapped[str] = mapped_column(String(24))
    actor_id: Mapped[str | None] = mapped_column(String(320))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Webhook(Base, TimestampMixin):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(
        ForeignKey(f"{SCHEMA}.organisations.id", ondelete="CASCADE")
    )
    event_type_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.event_types.id", ondelete="CASCADE")
    )
    subscriber_url: Mapped[str] = mapped_column(String(1000))
    encrypted_secret: Mapped[bytes | None] = mapped_column(LargeBinary)
    events: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("outbox_pending", "processed_at", "available_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(64), index=True)
    topic: Mapped[str] = mapped_column(String(80))
    aggregate_id: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class SuiteTicketRedemption(Base):
    __tablename__ = "suite_ticket_redemptions"

    jti_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
