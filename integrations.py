"""Optional Cal.com and Calendly v2 interoperability adapters."""
from __future__ import annotations

import os
import urllib.parse
import urllib.request
import json


def _request(url: str, token: str, *, method: str = "GET", payload: dict | None = None,
             extra_headers: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if data:
        headers["Content-Type"] = "application/json"
    headers.update(extra_headers or {})
    with urllib.request.urlopen(
        urllib.request.Request(url, data=data, method=method, headers=headers), timeout=20
    ) as response:
        return json.loads(response.read())


def calcom_event_types(token: str | None = None) -> list[dict]:
    token = token or os.getenv("CALCOM_API_TOKEN", "")
    if not token:
        return []
    body = _request(
        "https://api.cal.com/v2/event-types",
        token,
        extra_headers={"cal-api-version": "2024-06-14"},
    )
    return body.get("data", [])


def calendly_event_types(user_uri: str, token: str | None = None) -> list[dict]:
    token = token or os.getenv("CALENDLY_API_TOKEN", "")
    if not token:
        return []
    url = "https://api.calendly.com/event_types?" + urllib.parse.urlencode({"user": user_uri})
    return _request(url, token).get("collection", [])


def calendly_available_times(event_type_uri: str, start_time: str, end_time: str,
                             token: str | None = None) -> list[dict]:
    token = token or os.getenv("CALENDLY_API_TOKEN", "")
    if not token:
        return []
    query = urllib.parse.urlencode({
        "event_type": event_type_uri,
        "start_time": start_time,
        "end_time": end_time,
    })
    return _request(f"https://api.calendly.com/event_type_available_times?{query}", token).get("collection", [])
