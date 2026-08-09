"""Versioned FastCal API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select

from fastcal import __version__
from fastcal.config import settings
from fastcal.db.base import session_scope
from fastcal.db.models import Booking, EventType, Organisation
from fastcal.services.delivery import finalize_booking
from fastcal.services.scheduling import available_slots, create_booking

bearer = HTTPBearer(auto_error=False)


class Principal(BaseModel):
    subject: str
    organisation_id: str
    role: str


class BookingCreate(BaseModel):
    organisation_slug: str
    event_type_slug: str
    starts_at: datetime
    ends_at: datetime
    guest_name: str = Field(min_length=1, max_length=160)
    guest_email: str = Field(min_length=3, max_length=320)
    guest_timezone: str = "Europe/Tallinn"
    responses: dict[str, Any] = Field(default_factory=dict)
    attendees: list[dict[str, Any]] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, max_length=160)


def principal(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer),
) -> Principal:
    token = credentials.credentials if credentials else ""
    try:
        encoded, supplied = token.split(".", 1)
        expected = hmac.new(
            settings.FASTOFFICE_SSO_SECRET.encode(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        body = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if (
            not settings.FASTOFFICE_SSO_SECRET
            or not hmac.compare_digest(expected, supplied)
            or body.get("aud") != "calendar"
            or body.get("exp", 0) < int(datetime.now(UTC).timestamp())
        ):
            raise ValueError
        return Principal(
            subject=str(body["sub"]),
            organisation_id=str(body["org_id"]),
            role=str(body.get("role", "member")),
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=401, detail="A valid FastOffice calendar grant is required"
        ) from None


api = FastAPI(
    title="FastCal API",
    version=__version__,
    description="Team scheduling, availability, round-robin assignment, and public bookings.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    servers=[{"url": f"{settings.FASTCAL_PUBLIC_URL.rstrip('/')}/api"}],
)


@api.get("/v1/health", tags=["System"])
def health() -> dict[str, str]:
    return {"status": "ok", "product": "FastCal", "version": __version__}


def _event_type(db, organisation_slug: str, event_type_slug: str) -> EventType | None:
    return db.scalar(
        select(EventType)
        .join(Organisation, Organisation.id == EventType.organisation_id)
        .where(
            Organisation.slug == organisation_slug,
            EventType.slug == event_type_slug,
            EventType.active.is_(True),
        )
    )


@api.get("/v1/event-types/{organisation_slug}/{event_type_slug}", tags=["Event types"])
def get_event_type(organisation_slug: str, event_type_slug: str) -> dict[str, Any]:
    with session_scope() as db:
        item = _event_type(db, organisation_slug, event_type_slug)
        if item is None:
            raise HTTPException(status_code=404, detail="Event type not found")
        return {
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "duration_minutes": item.duration_minutes,
            "timezone": item.timezone,
            "scheduling_type": item.scheduling_type,
            "booking_fields": item.booking_fields,
        }


@api.get(
    "/v1/event-types/{organisation_slug}/{event_type_slug}/slots", tags=["Availability"]
)
def get_slots(
    organisation_slug: str,
    event_type_slug: str,
    days: int = Query(default=21, ge=1, le=60),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    with session_scope() as db:
        item = _event_type(db, organisation_slug, event_type_slug)
        if item is None:
            raise HTTPException(status_code=404, detail="Event type not found")
        slots = available_slots(db, item, now, now + timedelta(days=days))
        return {
            "data": [
                {"starts_at": slot.starts_at, "ends_at": slot.ends_at}
                for slot in slots[:200]
            ]
        }


@api.post("/v1/bookings", status_code=201, tags=["Bookings"])
def post_booking(payload: BookingCreate) -> dict[str, Any]:
    with session_scope() as db:
        item = _event_type(db, payload.organisation_slug, payload.event_type_slug)
        if item is None:
            raise HTTPException(status_code=404, detail="Event type not found")
        try:
            created = create_booking(
                db,
                event_type=item,
                starts_at=payload.starts_at,
                ends_at=payload.ends_at,
                guest_name=payload.guest_name,
                guest_email=payload.guest_email,
                guest_timezone=payload.guest_timezone,
                responses=payload.responses,
                attendees=payload.attendees,
                idempotency_key=payload.idempotency_key,
            )
            booking_id = created.booking.id
            booking_uid = created.booking.uid
            status = created.booking.status
            cancel_token = created.cancel_token
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    finalize_booking(booking_id, cancel_token)
    return {"id": booking_id, "uid": booking_uid, "status": status}


@api.get("/v1/bookings", tags=["Bookings"])
def list_bookings(auth: Principal = Depends(principal)) -> dict[str, Any]:
    with session_scope() as db:
        rows = db.scalars(
            select(Booking)
            .where(Booking.organisation_id == auth.organisation_id)
            .order_by(Booking.starts_at.desc())
            .limit(200)
        ).all()
        return {
            "data": [
                {
                    "id": row.id,
                    "uid": row.uid,
                    "title": row.title,
                    "starts_at": row.starts_at,
                    "ends_at": row.ends_at,
                    "status": row.status,
                    "guest_name": row.guest_name,
                    "guest_email": row.guest_email,
                }
                for row in rows
            ]
        }
