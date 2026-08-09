"""FastCal FastHTML application and mounted FastAPI."""

from __future__ import annotations

import re
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fasthtml.common import *  # noqa: F403
from sqlalchemy import delete, select, text
from starlette.responses import JSONResponse, RedirectResponse, Response

import views as legacy_views
from developer import developer_page
from fastcal import __version__
from fastcal.api import api
from fastcal.auth import google, suite
from fastcal.auth.provision import provision_identity, session_identity
from fastcal.config import settings
from fastcal.db.base import session_scope
from fastcal.db.models import (
    AvailabilityRule,
    Booking,
    EventType,
    EventTypeHost,
    Membership,
    Organisation,
    Schedule,
    Team,
    TeamMember,
    User,
)
from fastcal.services.delivery import finalize_booking
from fastcal.services.scheduling import available_slots, cancel_booking, create_booking
from fastcal.ui import views
from seo import register_seo_routes

app, rt = fast_app(live=False, pico=False, secret_key=settings.FASTCAL_SECRET)
app.mount("/api", api)


def identity(session) -> dict | None:
    return session.get("identity")


def require_identity(session):
    return identity(session) or RedirectResponse("/", status_code=303)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:80] or "meeting"


def _parse_datetime(value: str, timezone: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed.astimezone(UTC)


def _public_event(db, organisation_slug: str, event_slug: str):
    row = db.execute(
        select(EventType, Organisation)
        .join(Organisation, Organisation.id == EventType.organisation_id)
        .where(
            Organisation.slug == organisation_slug,
            EventType.slug == event_slug,
            EventType.active.is_(True),
        )
    ).first()
    return row if row else (None, None)


@rt("/health")
def get():
    return JSONResponse({"status": "ok", "product": "FastCal", "version": __version__})


@rt("/ready")
def get():
    try:
        with session_scope() as db:
            db.execute(text("SELECT 1"))
        return JSONResponse({"status": "ready", "product": "FastCal"})
    except Exception:
        return JSONResponse(
            {"status": "not_ready", "product": "FastCal"}, status_code=503
        )


@rt("/favicon.ico")
def get():
    return Response(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="15" fill="#0891b2"/><path d="M18 15h28v34H18z" fill="white"/><path d="M18 25h28M26 12v8M38 12v8" stroke="#0891b2" stroke-width="5"/></svg>',
        media_type="image/svg+xml",
    )


@rt("/swagger.json")
def get():
    return JSONResponse(api.openapi())


@rt("/developers")
def get():
    return developer_page()


@rt("/")
def get(session, auth: str = ""):
    if identity(session):
        return RedirectResponse("/app", status_code=303)
    return legacy_views.landing()


@rt("/auth/google")
def get(session, request):
    if not settings.google_enabled:
        return RedirectResponse("/?auth=google-not-configured", status_code=303)
    state = google.new_state()
    session["google_oauth_state"] = state
    return RedirectResponse(google.start_url(request, state), status_code=303)


@rt("/auth/google/callback")
def get(session, request, code: str = "", state: str = "", error: str = ""):
    expected = session.pop("google_oauth_state", None)
    if (
        error
        or not code
        or not state
        or not expected
        or not __import__("hmac").compare_digest(state, expected)
    ):
        return RedirectResponse("/?auth=google-failed", status_code=303)
    who = google.exchange(request, code)
    if who is None:
        return RedirectResponse("/?auth=google-denied", status_code=303)
    session["identity"] = who
    return RedirectResponse("/app", status_code=303)


@rt("/auth/suite")
def get():
    return RedirectResponse(
        f"{settings.FASTOFFICE_URL.rstrip('/')}/launch/calendar", status_code=303
    )


@rt("/auth/suite/callback")
def get(session, ticket: str = ""):
    who = suite.redeem(ticket)
    if who is None:
        return RedirectResponse("/?auth=suite-invalid", status_code=303)
    session["identity"] = who
    return RedirectResponse("/app", status_code=303)


@rt("/auth/dev")
def get():
    if settings.production or not settings.FASTCAL_DEV_LOGIN:
        return RedirectResponse("/", status_code=303)
    return Form(
        H1("FastCal development sign-in"),
        Input(name="email", type="email", value="developer@example.com", required=True),
        Button("Continue", type="submit"),
        method="post",
        action="/auth/dev",
    )


@rt("/auth/dev")
def post(session, email: str = "developer@example.com"):
    if settings.production or not settings.FASTCAL_DEV_LOGIN:
        return RedirectResponse("/", status_code=303)
    with session_scope() as db:
        user, organisation = provision_identity(
            db,
            email=email,
            name=email.split("@", 1)[0].replace(".", " ").title(),
            provider="google",
            provider_subject=f"dev:{email}",
        )
        who = session_identity(user, organisation, "owner")
    session["identity"] = who
    return RedirectResponse("/app", status_code=303)


@rt("/logout")
def get(session):
    session.clear()
    return RedirectResponse("/", status_code=303)


@rt("/app")
def get(session):
    who = require_identity(session)
    if isinstance(who, RedirectResponse):
        return who
    now = datetime.now(UTC)
    with session_scope() as db:
        organisation = db.get(Organisation, who["org_id"])
        event_types = db.scalars(
            select(EventType)
            .where(EventType.organisation_id == who["org_id"])
            .order_by(EventType.created_at.desc())
        ).all()
        for item in event_types:
            item.organisation_slug = organisation.slug
        upcoming = db.scalars(
            select(Booking)
            .where(
                Booking.organisation_id == who["org_id"],
                Booking.ends_at >= now,
            )
            .order_by(Booking.starts_at)
            .limit(10)
        ).all()
        return views.dashboard(who, event_types, upcoming)


@rt("/bookings")
def get(session):
    who = require_identity(session)
    if isinstance(who, RedirectResponse):
        return who
    with session_scope() as db:
        rows = db.scalars(
            select(Booking)
            .where(Booking.organisation_id == who["org_id"])
            .order_by(Booking.starts_at.desc())
            .limit(250)
        ).all()
        return views.page(who, "bookings", H1("Bookings"), views.booking_table(rows))


@rt("/event-types/new")
def get(session):
    who = require_identity(session)
    if isinstance(who, RedirectResponse):
        return who
    with session_scope() as db:
        schedules = db.scalars(
            select(Schedule).where(Schedule.user_id == who["sub"])
        ).all()
        teams = db.scalars(
            select(Team).where(Team.organisation_id == who["org_id"])
        ).all()
        users = db.scalars(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.organisation_id == who["org_id"])
        ).all()
        return views.event_type_form(who, schedules, teams, users)


@rt("/event-types")
def post(
    session,
    title: str,
    description: str = "",
    duration_minutes: int = 30,
    scheduling_type: str = "individual",
    schedule_id: str = "",
    team_id: str = "",
    host_emails: str = "",
    minimum_notice_minutes: int = 240,
    after_buffer_minutes: int = 10,
    location_type: str = "fastmeet",
):
    who = require_identity(session)
    if isinstance(who, RedirectResponse):
        return who
    if scheduling_type not in {"individual", "collective", "round_robin"}:
        return Response("Invalid scheduling type", status_code=422)
    with session_scope() as db:
        owner = db.get(User, who["sub"])
        schedule = db.scalar(
            select(Schedule).where(
                Schedule.id == schedule_id,
                Schedule.user_id == who["sub"],
            )
        )
        if owner is None or schedule is None:
            return Response("Schedule not found", status_code=422)
        base_slug = _slug(title)
        slug = base_slug
        suffix = 1
        while db.scalar(
            select(EventType.id).where(
                EventType.organisation_id == who["org_id"], EventType.slug == slug
            )
        ):
            suffix += 1
            slug = f"{base_slug[:72]}-{suffix}"
        if team_id and not db.scalar(
            select(Team.id).where(
                Team.id == team_id, Team.organisation_id == who["org_id"]
            )
        ):
            return Response("Team not found", status_code=422)
        event_type = EventType(
            organisation_id=who["org_id"],
            owner_id=who["sub"],
            team_id=team_id or None,
            schedule_id=schedule.id,
            title=title.strip()[:160],
            slug=slug,
            description=description.strip()[:4000],
            duration_minutes=max(5, min(480, duration_minutes)),
            timezone=schedule.timezone,
            scheduling_type=scheduling_type,
            minimum_notice_minutes=max(0, minimum_notice_minutes),
            after_buffer_minutes=max(0, after_buffer_minutes),
            location_type=location_type,
        )
        db.add(event_type)
        db.flush()
        requested = {
            email.strip().lower() for email in host_emails.split(",") if email.strip()
        }
        if not requested:
            requested = {owner.email}
        hosts = db.scalars(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.organisation_id == who["org_id"],
                User.email.in_(requested),
            )
        ).all()
        if len(hosts) != len(requested):
            return Response(
                "Every host must be a member of this workspace", status_code=422
            )
        for host in hosts:
            host_schedule = db.scalar(
                select(Schedule).where(
                    Schedule.user_id == host.id,
                    Schedule.is_default.is_(True),
                )
            )
            db.add(
                EventTypeHost(
                    event_type_id=event_type.id,
                    user_id=host.id,
                    schedule_id=host_schedule.id if host_schedule else schedule.id,
                )
            )
    return RedirectResponse("/app", status_code=303)


@rt("/availability")
def get(session, saved: int = 0):
    who = require_identity(session)
    if isinstance(who, RedirectResponse):
        return who
    with session_scope() as db:
        schedule = db.scalar(
            select(Schedule).where(
                Schedule.user_id == who["sub"], Schedule.is_default.is_(True)
            )
        )
        rules = db.scalars(
            select(AvailabilityRule)
            .where(AvailabilityRule.schedule_id == schedule.id)
            .order_by(AvailabilityRule.weekday)
        ).all()
        return views.availability_page(who, schedule, rules, bool(saved))


@rt("/availability")
def post(
    session,
    weekdays: str = "0,1,2,3,4",
    start_time: str = "09:00",
    end_time: str = "17:00",
    timezone: str = "Europe/Tallinn",
):
    who = require_identity(session)
    if isinstance(who, RedirectResponse):
        return who
    try:
        days = sorted({int(item.strip()) for item in weekdays.split(",")})
        if not days or any(day < 0 or day > 6 for day in days):
            raise ValueError
        start = time.fromisoformat(start_time)
        end = time.fromisoformat(end_time)
        if end <= start:
            raise ValueError
        ZoneInfo(timezone)
    except ValueError:
        return Response("Invalid availability", status_code=422)
    with session_scope() as db:
        schedule = db.scalar(
            select(Schedule).where(
                Schedule.user_id == who["sub"], Schedule.is_default.is_(True)
            )
        )
        schedule.timezone = timezone
        db.execute(
            delete(AvailabilityRule).where(AvailabilityRule.schedule_id == schedule.id)
        )
        for day in days:
            db.add(
                AvailabilityRule(
                    schedule_id=schedule.id,
                    weekday=day,
                    start_time=start,
                    end_time=end,
                )
            )
    return RedirectResponse("/availability?saved=1", status_code=303)


@rt("/teams")
def get(session, created: int = 0):
    who = require_identity(session)
    if isinstance(who, RedirectResponse):
        return who
    with session_scope() as db:
        teams = db.scalars(
            select(Team)
            .where(Team.organisation_id == who["org_id"])
            .order_by(Team.name)
        ).all()
        members = db.scalars(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.organisation_id == who["org_id"])
        ).all()
        return views.teams_page(who, teams, members, "Team created." if created else "")


@rt("/teams")
def post(session, name: str, member_emails: str = ""):
    who = require_identity(session)
    if isinstance(who, RedirectResponse):
        return who
    if who["role"] not in {"owner", "admin"}:
        return Response("Forbidden", status_code=403)
    with session_scope() as db:
        base_slug = _slug(name)
        slug = base_slug
        suffix = 1
        while db.scalar(
            select(Team.id).where(
                Team.organisation_id == who["org_id"], Team.slug == slug
            )
        ):
            suffix += 1
            slug = f"{base_slug[:72]}-{suffix}"
        team = Team(organisation_id=who["org_id"], name=name.strip()[:160], slug=slug)
        db.add(team)
        db.flush()
        emails = {
            who["email"],
            *[
                item.strip().lower()
                for item in member_emails.split(",")
                if item.strip()
            ],
        }
        for email in emails:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email, name=email.split("@", 1)[0].replace(".", " ").title()
                )
                db.add(user)
                db.flush()
            membership = db.scalar(
                select(Membership).where(
                    Membership.organisation_id == who["org_id"],
                    Membership.user_id == user.id,
                )
            )
            if membership is None:
                db.add(
                    Membership(
                        organisation_id=who["org_id"],
                        user_id=user.id,
                        role="member",
                        accepted=False,
                    )
                )
            db.add(
                TeamMember(
                    team_id=team.id,
                    user_id=user.id,
                    role="owner" if user.id == who["sub"] else "member",
                )
            )
    return RedirectResponse("/teams?created=1", status_code=303)


@rt("/book/{organisation_slug}/{event_slug}")
def get(
    organisation_slug: str,
    event_slug: str,
    starts_at: str = "",
    ends_at: str = "",
):
    with session_scope() as db:
        event_type, organisation = _public_event(db, organisation_slug, event_slug)
        if event_type is None:
            return Response("Booking page not found", status_code=404)
        if starts_at and ends_at:
            try:
                start = _parse_datetime(starts_at, event_type.timezone)
                end = _parse_datetime(ends_at, event_type.timezone)
            except ValueError:
                return Response("Invalid booking time", status_code=422)
            return views.public_booking_details(event_type, organisation, start, end)
        now = datetime.now(UTC)
        slots = available_slots(
            db,
            event_type,
            now,
            now + timedelta(days=event_type.future_limit_days),
        )
        return views.public_booking(event_type, organisation, slots)


@rt("/book/{organisation_slug}/{event_slug}")
def post(
    session,
    organisation_slug: str,
    event_slug: str,
    guest_name: str,
    guest_email: str,
    starts_at: str,
    ends_at: str,
    guest_timezone: str = "Europe/Tallinn",
    notes: str = "",
):
    with session_scope() as db:
        event_type, organisation = _public_event(db, organisation_slug, event_slug)
        if event_type is None:
            return Response("Booking page not found", status_code=404)
        try:
            start = _parse_datetime(starts_at, event_type.timezone)
            end = _parse_datetime(ends_at, event_type.timezone)
        except ValueError:
            return Response("Invalid booking time", status_code=422)
        try:
            created = create_booking(
                db,
                event_type=event_type,
                starts_at=start,
                ends_at=end,
                guest_name=guest_name,
                guest_email=guest_email,
                guest_timezone=guest_timezone,
                responses={"notes": notes.strip()[:4000]},
            )
            booking_id = created.booking.id
            booking_uid = created.booking.uid
            cancel_token = created.cancel_token
        except (ValueError, KeyError) as exc:
            return views.public_booking_details(
                event_type, organisation, start, end, str(exc)
            )
    tokens = session.setdefault("booking_cancel_tokens", {})
    tokens[booking_uid] = cancel_token
    session["booking_cancel_tokens"] = tokens
    finalize_booking(booking_id, cancel_token)
    return RedirectResponse(f"/booking/{booking_uid}/success", status_code=303)


@rt("/booking/{uid}/success")
def get(session, uid: str):
    with session_scope() as db:
        booking = db.scalar(select(Booking).where(Booking.uid == uid))
        if booking is None:
            return Response("Booking not found", status_code=404)
        token = session.get("booking_cancel_tokens", {}).get(uid, "")
        return views.booking_success(booking, token)


@rt("/bookings/cancel/{token}")
def get(token: str):
    return Html(
        Head(Title("Cancel booking"), Style(views.APP_CSS)),
        Body(
            Main(
                Div(
                    H1("Cancel this booking?"),
                    Form(
                        Button("Cancel booking", type="submit", cls="btn"),
                        method="post",
                    ),
                    cls="card",
                ),
                cls="booking-wrap",
            )
        ),
    )


@rt("/bookings/cancel/{token}")
def post(token: str, reason: str = ""):
    with session_scope() as db:
        booking = cancel_booking(db, token, reason)
        if booking is None:
            return Response(
                "This cancellation link is invalid or already used", status_code=404
            )
    return Html(
        Head(Title("Booking cancelled"), Style(views.APP_CSS)),
        Body(
            Main(
                Div(
                    H1("Booking cancelled."),
                    P("The host has been notified."),
                    cls="card",
                ),
                cls="booking-wrap",
            )
        ),
    )


register_seo_routes(app)
