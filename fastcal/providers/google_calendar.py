"""Google Calendar availability and event adapter."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from fastcal.auth.crypto import decrypt, encrypt
from fastcal.config import settings
from fastcal.db.models import CalendarConnection, OAuthCredential

TOKEN_URL = "https://oauth2.googleapis.com/token"
FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"


def _access_token(db: Session, credential: OAuthCredential) -> str:
    now = datetime.now(UTC)
    current = decrypt(credential.encrypted_access_token)
    if (
        current
        and credential.expires_at
        and credential.expires_at > now + timedelta(minutes=2)
    ):
        return current
    refresh_token = decrypt(credential.encrypted_refresh_token)
    if not refresh_token:
        credential.invalid = True
        return ""
    try:
        response = httpx.post(
            TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        current = payload["access_token"]
    except (httpx.HTTPError, KeyError, ValueError):
        credential.invalid = True
        return ""
    credential.encrypted_access_token = encrypt(current)
    credential.expires_at = now + timedelta(
        seconds=int(payload.get("expires_in", 3600))
    )
    credential.invalid = False
    db.flush()
    return current


def busy_for_users(
    db: Session,
    user_ids: list[str],
    starts_at: datetime,
    ends_at: datetime,
) -> dict[str, list[tuple[datetime, datetime]]]:
    result: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    if not user_ids:
        return result
    connections = db.scalars(
        select(CalendarConnection).where(
            CalendarConnection.user_id.in_(user_ids),
            CalendarConnection.provider == "google",
            CalendarConnection.selected_for_conflicts.is_(True),
        )
    ).all()
    by_credential: dict[str, list[CalendarConnection]] = defaultdict(list)
    for connection in connections:
        if connection.credential_id:
            by_credential[connection.credential_id].append(connection)
    for credential_id, calendars in by_credential.items():
        credential = db.get(OAuthCredential, credential_id)
        if credential is None or credential.invalid:
            continue
        token = _access_token(db, credential)
        if not token:
            continue
        try:
            response = httpx.post(
                FREEBUSY_URL,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "timeMin": starts_at.astimezone(UTC).isoformat(),
                    "timeMax": ends_at.astimezone(UTC).isoformat(),
                    "items": [{"id": row.external_id} for row in calendars],
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json().get("calendars", {})
        except (httpx.HTTPError, ValueError):
            continue
        for connection in calendars:
            for period in payload.get(connection.external_id, {}).get("busy", []):
                try:
                    start = datetime.fromisoformat(
                        period["start"].replace("Z", "+00:00")
                    )
                    end = datetime.fromisoformat(period["end"].replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    continue
                result[connection.user_id].append((start, end))
    return result


def create_event(
    db: Session,
    *,
    host_id: str,
    title: str,
    description: str,
    starts_at: datetime,
    ends_at: datetime,
    timezone: str,
    location: str,
    attendee_emails: list[str],
) -> str | None:
    destination = db.scalar(
        select(CalendarConnection).where(
            CalendarConnection.user_id == host_id,
            CalendarConnection.provider == "google",
            CalendarConnection.destination.is_(True),
        )
    )
    if destination is None or not destination.credential_id:
        return None
    credential = db.get(OAuthCredential, destination.credential_id)
    if credential is None:
        return None
    token = _access_token(db, credential)
    if not token:
        return None
    try:
        response = httpx.post(
            EVENTS_URL.format(calendar_id=quote(destination.external_id, safe="")),
            params={"sendUpdates": "all"},
            headers={"Authorization": f"Bearer {token}"},
            json={
                "summary": title,
                "description": description,
                "location": location,
                "start": {"dateTime": starts_at.isoformat(), "timeZone": timezone},
                "end": {"dateTime": ends_at.isoformat(), "timeZone": timezone},
                "attendees": [
                    {"email": email} for email in sorted(set(attendee_emails))
                ],
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json().get("id")
    except (httpx.HTTPError, ValueError):
        return None
