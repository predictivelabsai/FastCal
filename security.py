"""FastOffice suite-ticket verification with local replay protection."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

import db


def verify_ticket(token: str, audience: str = "calendar") -> dict | None:
    secret = os.getenv("FASTOFFICE_SSO_SECRET", "")
    if not secret:
        return None
    try:
        encoded, supplied = token.split(".", 1)
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            return None
        body = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        now = int(time.time())
        if body.get("aud") != audience or body.get("exp", 0) < now or not body.get("jti"):
            return None
        jti_hash = hashlib.sha256(body["jti"].encode()).hexdigest()
        with db.connect() as con:
            con.execute("DELETE FROM redeemed_tickets WHERE expires_at<?", (now,))
            if con.execute("SELECT 1 FROM redeemed_tickets WHERE jti_hash=?", (jti_hash,)).fetchone():
                return None
            con.execute("INSERT INTO redeemed_tickets(jti_hash,expires_at,redeemed_at) VALUES(?,?,?)",
                        (jti_hash, body["exp"], now))
        required = {"sub", "email", "name", "org_id", "org_name", "role"}
        return body if required.issubset(body) else None
    except (ValueError, TypeError, json.JSONDecodeError, KeyError):
        return None
