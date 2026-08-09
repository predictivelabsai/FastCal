"""FastMeet meeting-room adapter."""

from __future__ import annotations

import secrets
from datetime import datetime

import httpx

from fastcal.auth.suite import sign_service_ticket
from fastcal.config import settings


def create_meeting(
    *,
    identity: dict,
    title: str,
    starts_at: datetime,
    duration_minutes: int,
    agenda: str,
) -> tuple[str | None, str]:
    room_code = f"cal-{secrets.token_urlsafe(9)}"
    if not settings.FASTOFFICE_SSO_SECRET:
        return None, ""
    ticket = sign_service_ticket(identity, "meet")
    try:
        response = httpx.post(
            f"{settings.FASTMEET_URL.rstrip('/')}/api/v1/meetings",
            headers={"Authorization": f"Bearer {ticket}"},
            json={
                "title": title,
                "host": identity["email"],
                "start_time": starts_at.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_min": duration_minutes,
                "status": "Scheduled",
                "room_code": room_code,
                "agenda": agenda,
                "has_recording": 0,
            },
            timeout=20,
        )
        response.raise_for_status()
        meeting_id = str(response.json()["id"])
        return meeting_id, f"{settings.FASTMEET_URL.rstrip('/')}/room/{meeting_id}"
    except (httpx.HTTPError, KeyError, ValueError):
        return None, ""
