"""Encryption helpers for provider and webhook credentials."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from fastcal.config import settings


def _fernet() -> Fernet:
    configured = settings.FASTCAL_ENCRYPTION_KEY.encode()
    try:
        return Fernet(configured)
    except (ValueError, TypeError):
        material = configured or settings.FASTCAL_SECRET.encode()
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(material).digest()))


def encrypt(value: str | None) -> bytes | None:
    return _fernet().encrypt(value.encode()) if value else None


def decrypt(value: bytes | None) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value).decode()
    except InvalidToken:
        return ""
