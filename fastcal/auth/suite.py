"""Replay-safe FastOffice SSO redemption and service ticket signing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from fastcal.auth.provision import provision_identity, session_identity
from fastcal.config import settings
from fastcal.db.base import session_scope
from fastcal.db.models import SuiteTicketRedemption


def _decode(token: str, audience: str) -> dict | None:
    if not settings.FASTOFFICE_SSO_SECRET:
        return None
    try:
        encoded, supplied = token.split(".", 1)
        expected = hmac.new(
            settings.FASTOFFICE_SSO_SECRET.encode(), encoded.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            return None
        body = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        required = {
            "sub",
            "email",
            "name",
            "org_id",
            "org_name",
            "role",
            "jti",
            "exp",
            "aud",
        }
        now = int(datetime.now(UTC).timestamp())
        if (
            not required.issubset(body)
            or body["aud"] != audience
            or int(body["exp"]) < now
        ):
            return None
        return body
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def redeem(token: str, audience: str = "calendar") -> dict | None:
    body = _decode(token, audience)
    if body is None:
        return None
    digest = hashlib.sha256(body["jti"].encode()).hexdigest()
    expiry = datetime.fromtimestamp(int(body["exp"]), UTC)
    try:
        with session_scope() as db:
            db.add(SuiteTicketRedemption(jti_hash=digest, expires_at=expiry))
            user, organisation = provision_identity(
                db,
                email=body["email"],
                name=body["name"],
                provider="fastoffice",
                provider_subject=str(body["sub"]),
                organisation_id=str(body["org_id"]),
                organisation_name=body["org_name"],
                role=body["role"],
            )
            return session_identity(user, organisation, body["role"])
    except IntegrityError:
        return None


def sign_service_ticket(identity: dict, audience: str, ttl_seconds: int = 60) -> str:
    now = datetime.now(UTC)
    body = {
        "sub": identity["sub"],
        "email": identity["email"],
        "name": identity["name"],
        "org_id": identity["org_id"],
        "org_name": identity["org_name"],
        "role": identity.get("role", "member"),
        "aud": audience,
        "jti": secrets.token_urlsafe(16),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    encoded = (
        base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    signature = hmac.new(
        settings.FASTOFFICE_SSO_SECRET.encode(), encoded.encode(), hashlib.sha256
    ).hexdigest()
    return f"{encoded}.{signature}"
