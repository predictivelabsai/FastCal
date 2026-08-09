"""Transactional booking email delivery through Postmark."""

from __future__ import annotations

import html
import re

import httpx

from fastcal.config import settings


def send(to: str, subject: str, html_body: str) -> bool:
    if not settings.POSTMARK_API_TOKEN or not settings.FROM_EMAIL:
        return False
    try:
        response = httpx.post(
            "https://api.postmarkapp.com/email",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": settings.POSTMARK_API_TOKEN,
            },
            json={
                "From": settings.FROM_EMAIL,
                "To": to,
                "Subject": subject,
                "HtmlBody": html_body,
                "TextBody": re.sub(r"<[^>]+>", "", html_body),
                "MessageStream": "outbound",
            },
            timeout=20,
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def booking_confirmation(
    *,
    to: str,
    guest_name: str,
    title: str,
    when: str,
    location: str,
    cancel_url: str,
) -> bool:
    body = (
        f"<p>Hello {html.escape(guest_name)},</p>"
        f"<p>Your booking for <strong>{html.escape(title)}</strong> is confirmed.</p>"
        f"<p>{html.escape(when)}<br>{html.escape(location)}</p>"
        f'<p><a href="{html.escape(cancel_url, quote=True)}">Cancel this booking</a></p>'
    )
    return send(to, f"Confirmed: {title}", body)
