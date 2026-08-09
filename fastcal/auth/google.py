"""Google OpenID Connect and Calendar OAuth flow."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy import select

from fastcal.auth.crypto import encrypt
from fastcal.auth.provision import provision_identity, session_identity
from fastcal.config import settings
from fastcal.db.base import session_scope
from fastcal.db.models import CalendarConnection, Membership, OAuthCredential

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
)


def callback_uri(request) -> str:
    if settings.GOOGLE_REDIRECT_URI:
        return settings.GOOGLE_REDIRECT_URI
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}/auth/google/callback"


def start_url(request, state: str) -> str:
    return (
        AUTH_URL
        + "?"
        + urlencode(
            {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": callback_uri(request),
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "state": state,
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent select_account",
            }
        )
    )


def new_state() -> str:
    return secrets.token_urlsafe(32)


def exchange(request, code: str) -> dict | None:
    try:
        with httpx.Client(timeout=20) as client:
            token_response = client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": callback_uri(request),
                    "grant_type": "authorization_code",
                },
            )
            token_response.raise_for_status()
            token = token_response.json()
            info_response = client.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {token['access_token']}"},
            )
            info_response.raise_for_status()
            info = info_response.json()
    except (httpx.HTTPError, KeyError, ValueError):
        return None

    email = (info.get("email") or "").strip().lower()
    if not email or info.get("email_verified") is False:
        return None
    domains = {
        item.strip().lower()
        for item in settings.GOOGLE_ALLOWED_DOMAINS.split(",")
        if item.strip()
    }
    emails = {
        item.strip().lower()
        for item in settings.GOOGLE_ALLOWED_EMAILS.split(",")
        if item.strip()
    }
    if domains or emails:
        if email not in emails and email.rsplit("@", 1)[-1] not in domains:
            return None

    expires_at = datetime.now(UTC) + timedelta(
        seconds=int(token.get("expires_in", 3600))
    )
    with session_scope() as db:
        user, organisation = provision_identity(
            db,
            email=email,
            name=info.get("name") or email,
            provider="google",
            provider_subject=str(info.get("sub") or email),
        )
        credential = db.scalar(
            select(OAuthCredential).where(
                OAuthCredential.user_id == user.id,
                OAuthCredential.provider == "google",
                OAuthCredential.provider_account_id
                == str(info.get("sub") or "primary"),
            )
        )
        if credential is None:
            credential = OAuthCredential(
                user_id=user.id,
                provider="google",
                provider_account_id=str(info.get("sub") or "primary"),
            )
            db.add(credential)
        credential.encrypted_access_token = encrypt(token.get("access_token"))
        if token.get("refresh_token"):
            credential.encrypted_refresh_token = encrypt(token["refresh_token"])
        credential.expires_at = expires_at
        credential.scopes = token.get("scope") or " ".join(SCOPES)
        credential.invalid = False
        db.flush()
        _sync_calendar_list(db, user.id, credential.id, token["access_token"])
        role = (
            db.scalar(
                select(Membership.role).where(
                    Membership.user_id == user.id,
                    Membership.organisation_id == organisation.id,
                )
            )
            or "owner"
        )
        identity = session_identity(user, organisation, role)
    return identity


def _sync_calendar_list(
    db, user_id: str, credential_id: str, access_token: str
) -> None:
    try:
        response = httpx.get(
            CALENDAR_LIST_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
        response.raise_for_status()
        calendars = response.json().get("items", [])
    except (httpx.HTTPError, ValueError):
        return
    for item in calendars:
        external_id = item.get("id")
        if not external_id:
            continue
        connection = db.scalar(
            select(CalendarConnection).where(
                CalendarConnection.user_id == user_id,
                CalendarConnection.provider == "google",
                CalendarConnection.external_id == external_id,
            )
        )
        if connection is None:
            connection = CalendarConnection(
                user_id=user_id,
                credential_id=credential_id,
                provider="google",
                external_id=external_id,
            )
            db.add(connection)
        connection.name = item.get("summary") or "Google Calendar"
        connection.selected_for_conflicts = bool(item.get("selected", True))
        connection.destination = bool(item.get("primary", False))
