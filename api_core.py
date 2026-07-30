"""FastCal API authentication primitives."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False, scheme_name="FastOffice tenant grant")


@dataclass(frozen=True)
class Principal:
    organisation_id: str
    subject: str
    role: str


def principal(credentials: HTTPAuthorizationCredentials | None = Security(bearer)) -> Principal:
    secret = os.getenv("FASTOFFICE_SSO_SECRET", "")
    token = credentials.credentials if credentials else ""
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        body = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if not secret or not hmac.compare_digest(signature, expected) or body.get("aud") != "calendar" or body.get("exp", 0) < int(time.time()):
            raise ValueError
        return Principal(str(body["org_id"]), str(body["sub"]), str(body.get("role", "member")))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail={"code": "invalid_token", "message": "A valid FastOffice tenant grant is required."})


def write_swagger(api, destination):
    from pathlib import Path
    Path(destination).write_text(json.dumps(api.openapi(), indent=2, sort_keys=True) + "\n")
