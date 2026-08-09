"""Post-booking calendar, FastMeet, and notification delivery."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import select

from fastcal.config import settings
from fastcal.db.base import session_scope
from fastcal.db.models import Booking, EventType, Membership, Organisation, User
from fastcal.providers.fastmeet import create_meeting
from fastcal.providers.google_calendar import create_event
from fastcal.providers.postmark import booking_confirmation
from fastcal.services.scheduling import booking_hosts


def finalize_booking(booking_id: str, cancel_token: str) -> None:
    with session_scope() as db:
        booking = db.get(Booking, booking_id)
        if booking is None or booking.status not in {"accepted", "pending"}:
            return
        event_type = db.get(EventType, booking.event_type_id)
        organisation = db.get(Organisation, booking.organisation_id)
        primary = db.get(User, booking.primary_host_id)
        hosts = booking_hosts(db, booking.id)
        if event_type is None or organisation is None or primary is None:
            return
        membership_role = (
            db.scalar(
                select(Membership.role).where(
                    Membership.organisation_id == organisation.id,
                    Membership.user_id == primary.id,
                )
            )
            or "member"
        )
        identity = {
            "sub": primary.id,
            "email": primary.email,
            "name": primary.name,
            "org_id": organisation.id,
            "org_name": organisation.name,
            "role": membership_role,
        }
        if event_type.location_type == "fastmeet" and not booking.meet_url:
            meeting_id, meeting_url = create_meeting(
                identity=identity,
                title=booking.title,
                starts_at=booking.starts_at,
                duration_minutes=event_type.duration_minutes,
                agenda=str(booking.responses.get("notes", "")),
            )
            if meeting_url:
                booking.fastmeet_meeting_id = meeting_id
                booking.meet_url = meeting_url
                booking.location = meeting_url
        attendee_emails = [booking.guest_email] + [
            host.email for host in hosts if host.id != primary.id
        ]
        if not booking.external_calendar_event_id:
            booking.external_calendar_event_id = create_event(
                db,
                host_id=primary.id,
                title=booking.title,
                description=str(booking.responses.get("notes", "")),
                starts_at=booking.starts_at,
                ends_at=booking.ends_at,
                timezone=event_type.timezone,
                location=booking.meet_url or booking.location,
                attendee_emails=attendee_emails,
            )
        guest_email = booking.guest_email
        guest_name = booking.guest_name
        title = booking.title
        timezone = booking.guest_timezone
        starts_at = booking.starts_at
        location = booking.meet_url or booking.location or "Details to follow"
    local = starts_at.astimezone(ZoneInfo(timezone))
    booking_confirmation(
        to=guest_email,
        guest_name=guest_name,
        title=title,
        when=local.strftime("%A, %d %B %Y at %H:%M %Z"),
        location=location,
        cancel_url=f"{settings.FASTCAL_PUBLIC_URL.rstrip('/')}/bookings/cancel/{cancel_token}",
    )
