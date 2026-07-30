"""FastCal — tenant-native open calendar for FastOffice."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote

from dotenv import load_dotenv
from fasthtml.common import *
from starlette.responses import JSONResponse, RedirectResponse, Response

load_dotenv()

import db
import views
from api import api
from developer import developer_page
from security import verify_ticket

app, rt = fast_app(secret_key=os.getenv("FASTCAL_SECRET", secrets.token_hex(32)))
app.mount("/api", api)


def identity(session):
    return session.get("identity")


def guard(session):
    return identity(session) or RedirectResponse("/auth/suite", status_code=303)


@rt("/")
def get(session):
    who = identity(session)
    return views.home(who, db.events(who["org_id"])) if who else views.landing()


@rt("/health")
def get():
    return JSONResponse({"status": "ok", "product": "FastCal"})


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


@rt("/auth/suite")
def get():
    office = os.getenv("FASTOFFICE_URL", "http://localhost:5020").rstrip("/")
    return RedirectResponse(f"{office}/launch/calendar", status_code=303)


@rt("/auth/suite/callback")
def get(session, ticket: str = ""):
    who = verify_ticket(ticket)
    if not who:
        return RedirectResponse("/?auth=invalid", status_code=303)
    db.provision(who)
    session["identity"] = {k: who[k] for k in ("sub", "email", "name", "org_id", "org_name", "role")}
    return RedirectResponse("/", status_code=303)


@rt("/auth/dev")
def post(session, email: str = "kaljuvee@gmail.com"):
    if os.getenv("FASTCAL_ENV", "development") == "production" or os.getenv("FASTCAL_DEV_LOGIN", "true").lower() not in {"1","true","yes"}:
        return RedirectResponse("/", status_code=303)
    who = {"sub": email, "email": email, "name": email.split("@")[0].title(), "org_id": "dev", "org_name": "Development", "role": "owner"}
    db.provision(who)
    session["identity"] = who
    return RedirectResponse("/", status_code=303)


@rt("/auth/dev")
def get():
    if os.getenv("FASTCAL_ENV", "development") == "production":
        return RedirectResponse("/", status_code=303)
    return Form(
        H1("FastCal development sign-in"),
        Input(name="email", type="email", value="kaljuvee@gmail.com", required=True),
        Button("Continue", type="submit"),
        method="post",
        action="/auth/dev",
    )


@rt("/logout")
def get(session):
    session.clear()
    return RedirectResponse("/", status_code=303)


@rt("/events/new")
def get(session):
    who = guard(session)
    return who if isinstance(who, RedirectResponse) else views.event_form(who, db.calendars(who["org_id"]))


@rt("/events")
def post(session, calendar_id: int, title: str, starts_at: str, ends_at: str, timezone: str = "Europe/Tallinn",
         reminder_minutes: int = 15, location: str = "", meet_url: str = "", attendees: str = "",
         recurrence: str = "", description: str = ""):
    who = guard(session)
    if isinstance(who, RedirectResponse):
        return who
    db.create_event(who, locals())
    return RedirectResponse("/", status_code=303)


@rt("/events/delete")
def post(session, event_id: int):
    who = guard(session)
    if not isinstance(who, RedirectResponse):
        db.delete_event(who, event_id)
    return RedirectResponse("/", status_code=303)


def available_slots(page: dict, days: int = 21) -> list[dict]:
    import json
    rules = json.loads(page["availability_json"])
    tz = ZoneInfo(page["timezone"])
    now = datetime.now(tz)
    earliest = now + timedelta(hours=page["minimum_notice_hours"])
    result = []
    cursor = now.date()
    day_codes = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    for offset in range(days):
        date = cursor + timedelta(days=offset)
        if day_codes[date.weekday()] not in rules["days"]:
            continue
        start = datetime.combine(date, datetime.strptime(rules["start"], "%H:%M").time(), tz)
        finish = datetime.combine(date, datetime.strptime(rules["end"], "%H:%M").time(), tz)
        while start + timedelta(minutes=page["duration_minutes"]) <= finish:
            end = start + timedelta(minutes=page["duration_minutes"])
            iso_start, iso_end = start.isoformat(), end.isoformat()
            if start >= earliest and not db.booked_ranges(page["id"], iso_start, iso_end):
                result.append({"starts_at": iso_start, "ends_at": iso_end, "label": start.strftime("%a %d %b · %H:%M")})
            start = end + timedelta(minutes=page["buffer_minutes"])
            if len(result) >= 60:
                return result
    return result


@rt("/booking-pages")
def get(session):
    who = guard(session)
    return who if isinstance(who, RedirectResponse) else views.booking_pages(who, db.booking_pages(who["org_id"]))


@rt("/booking-pages")
def post(session, title: str, duration_minutes: int = 30, available_from: str = "09:00",
         available_to: str = "17:00", timezone: str = "Europe/Tallinn", minimum_notice_hours: int = 4,
         buffer_minutes: int = 10, location: str = "", description: str = ""):
    who = guard(session)
    if isinstance(who, RedirectResponse):
        return who
    slug = db.create_booking_page(who, locals())
    return RedirectResponse(f"/book/{slug}", status_code=303)


@rt("/book/{slug}")
def get(slug: str, booked: int = 0):
    page = db.booking_page(slug)
    if not page:
        return "Booking page not found", 404
    return views.public_booking(page, available_slots(page), "Your meeting is confirmed." if booked else "")


@rt("/book/{slug}")
def post(slug: str, guest_name: str, guest_email: str, starts_at: str, ends_at: str, guest_notes: str = ""):
    page = db.booking_page(slug)
    if not page:
        return "Booking page not found", 404
    valid = {(slot["starts_at"], slot["ends_at"]) for slot in available_slots(page)}
    if (starts_at, ends_at) not in valid or "@" not in guest_email:
        return views.public_booking(page, available_slots(page), "That time is unavailable. Please choose another.")
    try:
        _, token = db.create_booking(page, locals())
    except ValueError:
        return views.public_booking(page, available_slots(page), "That time was just booked. Please choose another.")
    return RedirectResponse(f"/book/{slug}?booked=1", status_code=303, headers={"X-FastCal-Cancel-Token": token})


@rt("/bookings/cancel/{token}")
def get(token: str):
    db.cancel_booking(token)
    return RedirectResponse("/", status_code=303)


@rt("/api/v1/events")
def get(session, q: str = ""):
    who = guard(session)
    if isinstance(who, RedirectResponse):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse({"items": db.events(who["org_id"], q)})


@rt("/search")
def get(session, q: str = ""):
    who = guard(session)
    if isinstance(who, RedirectResponse):
        return who
    return views.home(who, db.events(who["org_id"], q))


if __name__ == "__main__":
    serve(port=int(os.getenv("FASTCAL_PORT", "5021")))
