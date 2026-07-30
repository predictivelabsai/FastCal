"""FastCal tenant-scoped persistence."""
from __future__ import annotations

import os
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.getenv("FASTCAL_DB", "data/fastcal.sqlite"))

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS organisations(
  id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships(
  user_id TEXT NOT NULL REFERENCES users(id), organisation_id TEXT NOT NULL REFERENCES organisations(id),
  role TEXT NOT NULL, PRIMARY KEY(user_id,organisation_id)
);
CREATE TABLE IF NOT EXISTS calendars(
  id INTEGER PRIMARY KEY, organisation_id TEXT NOT NULL REFERENCES organisations(id),
  name TEXT NOT NULL, colour TEXT NOT NULL DEFAULT '#0891b2', owner_id TEXT NOT NULL REFERENCES users(id),
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY, organisation_id TEXT NOT NULL REFERENCES organisations(id),
  calendar_id INTEGER NOT NULL REFERENCES calendars(id) ON DELETE CASCADE,
  title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '',
  starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, timezone TEXT NOT NULL DEFAULT 'Europe/Tallinn',
  recurrence TEXT NOT NULL DEFAULT '', attendees TEXT NOT NULL DEFAULT '',
  reminder_minutes INTEGER NOT NULL DEFAULT 15, meet_url TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL REFERENCES users(id), created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS redeemed_tickets(
  jti_hash TEXT PRIMARY KEY, expires_at INTEGER NOT NULL, redeemed_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS booking_pages(
  id INTEGER PRIMARY KEY, organisation_id TEXT NOT NULL REFERENCES organisations(id),
  owner_id TEXT NOT NULL REFERENCES users(id), slug TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '', duration_minutes INTEGER NOT NULL DEFAULT 30,
  timezone TEXT NOT NULL DEFAULT 'Europe/Tallinn', availability_json TEXT NOT NULL,
  minimum_notice_hours INTEGER NOT NULL DEFAULT 4, buffer_minutes INTEGER NOT NULL DEFAULT 10,
  location TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings(
  id INTEGER PRIMARY KEY, booking_page_id INTEGER NOT NULL REFERENCES booking_pages(id),
  organisation_id TEXT NOT NULL REFERENCES organisations(id), event_id INTEGER REFERENCES events(id),
  guest_name TEXT NOT NULL, guest_email TEXT NOT NULL, guest_notes TEXT NOT NULL DEFAULT '',
  starts_at TEXT NOT NULL, ends_at TEXT NOT NULL, timezone TEXT NOT NULL,
  cancel_token_hash TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'confirmed',
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS events_tenant_time ON events(organisation_id,starts_at);
CREATE INDEX IF NOT EXISTS bookings_page_time ON bookings(booking_page_id,starts_at,status);
"""


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init():
    with connect() as con:
        con.executescript(SCHEMA)


def provision(identity: dict) -> None:
    stamp = int(time.time())
    with connect() as con:
        con.execute("INSERT OR IGNORE INTO organisations(id,name,created_at) VALUES(?,?,?)",
                    (identity["org_id"], identity["org_name"], stamp))
        con.execute("""INSERT INTO users(id,email,name,created_at) VALUES(?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET email=excluded.email,name=excluded.name""",
                    (identity["sub"], identity["email"], identity["name"], stamp))
        con.execute("""INSERT INTO memberships(user_id,organisation_id,role) VALUES(?,?,?)
                       ON CONFLICT(user_id,organisation_id) DO UPDATE SET role=excluded.role""",
                    (identity["sub"], identity["org_id"], identity["role"]))
        exists = con.execute("SELECT 1 FROM calendars WHERE organisation_id=?", (identity["org_id"],)).fetchone()
        if not exists:
            con.execute("INSERT INTO calendars(organisation_id,name,owner_id,created_at) VALUES(?,?,?,?)",
                        (identity["org_id"], "Team calendar", identity["sub"], stamp))


def calendars(org_id: str) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM calendars WHERE organisation_id=? ORDER BY name", (org_id,))]


def events(org_id: str, query: str = "") -> list[dict]:
    with connect() as con:
        term = f"%{query.strip()}%"
        return [dict(r) for r in con.execute(
            """SELECT e.*,c.name calendar_name,c.colour FROM events e JOIN calendars c ON c.id=e.calendar_id
               WHERE e.organisation_id=? AND (?='' OR e.title LIKE ? OR e.description LIKE ? OR e.attendees LIKE ?)
               ORDER BY e.starts_at LIMIT 100""", (org_id, query.strip(), term, term, term))]


def create_event(identity: dict, payload: dict) -> int:
    allowed = {c["id"] for c in calendars(identity["org_id"])}
    calendar_id = int(payload.get("calendar_id") or 0)
    if calendar_id not in allowed:
        raise ValueError("calendar does not belong to organisation")
    stamp = int(time.time())
    with connect() as con:
        cur = con.execute(
            """INSERT INTO events(organisation_id,calendar_id,title,description,location,starts_at,ends_at,
               timezone,recurrence,attendees,reminder_minutes,meet_url,created_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (identity["org_id"], calendar_id, (payload.get("title") or "Untitled event")[:160],
             (payload.get("description") or "")[:2000], (payload.get("location") or "")[:300],
             payload["starts_at"], payload["ends_at"], payload.get("timezone") or "Europe/Tallinn",
             (payload.get("recurrence") or "")[:200], (payload.get("attendees") or "")[:1000],
             int(payload.get("reminder_minutes") or 15), (payload.get("meet_url") or "")[:500],
             identity["sub"], stamp, stamp))
        return int(cur.lastrowid)


def delete_event(identity: dict, event_id: int) -> bool:
    with connect() as con:
        cur = con.execute("DELETE FROM events WHERE id=? AND organisation_id=?",
                          (event_id, identity["org_id"]))
        return cur.rowcount == 1


def booking_pages(org_id: str) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM booking_pages WHERE organisation_id=? ORDER BY id DESC", (org_id,))]


def create_booking_page(identity: dict, payload: dict) -> str:
    base = "".join(c.lower() if c.isalnum() else "-" for c in payload["title"]).strip("-") or "meet"
    slug = f"{base[:36]}-{secrets.token_hex(3)}"
    availability = {
        "days": payload.get("days") or ["mon", "tue", "wed", "thu", "fri"],
        "start": payload.get("available_from") or "09:00",
        "end": payload.get("available_to") or "17:00",
    }
    with connect() as con:
        con.execute(
            """INSERT INTO booking_pages(organisation_id,owner_id,slug,title,description,duration_minutes,
               timezone,availability_json,minimum_notice_hours,buffer_minutes,location,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (identity["org_id"], identity["sub"], slug, payload["title"][:160],
             payload.get("description", "")[:1000], int(payload.get("duration_minutes") or 30),
             payload.get("timezone") or "Europe/Tallinn", json.dumps(availability),
             int(payload.get("minimum_notice_hours") or 4), int(payload.get("buffer_minutes") or 10),
             payload.get("location", "")[:300], int(time.time())))
    return slug


def booking_page(slug: str) -> dict | None:
    with connect() as con:
        row = con.execute(
            """SELECT p.*,u.name owner_name,u.email owner_email,o.name organisation_name
               FROM booking_pages p JOIN users u ON u.id=p.owner_id
               JOIN organisations o ON o.id=p.organisation_id WHERE p.slug=? AND p.active=1""",
            (slug,)).fetchone()
        return dict(row) if row else None


def booked_ranges(page_id: int, start: str, end: str) -> list[tuple[str, str]]:
    with connect() as con:
        return [(r["starts_at"], r["ends_at"]) for r in con.execute(
            """SELECT starts_at,ends_at FROM bookings WHERE booking_page_id=? AND status='confirmed'
               AND starts_at<? AND ends_at>?""", (page_id, end, start))]


def create_booking(page: dict, payload: dict) -> tuple[int, str]:
    """Atomically reserve a public slot and create its tenant-owned event."""
    import hashlib
    stamp = int(time.time())
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        conflict = con.execute(
            """SELECT 1 FROM bookings WHERE booking_page_id=? AND status='confirmed'
               AND starts_at<? AND ends_at>?""",
            (page["id"], payload["ends_at"], payload["starts_at"])).fetchone()
        if conflict:
            raise ValueError("slot is no longer available")
        calendar = con.execute(
            "SELECT id FROM calendars WHERE organisation_id=? AND owner_id=? ORDER BY id LIMIT 1",
            (page["organisation_id"], page["owner_id"])).fetchone()
        if not calendar:
            raise ValueError("host calendar unavailable")
        title = f"{page['title']} · {payload['guest_name']}"
        cur = con.execute(
            """INSERT INTO events(organisation_id,calendar_id,title,description,location,starts_at,ends_at,
               timezone,attendees,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (page["organisation_id"], calendar["id"], title, payload.get("guest_notes", "")[:2000],
             page["location"], payload["starts_at"], payload["ends_at"], page["timezone"],
             payload["guest_email"], page["owner_id"], stamp, stamp))
        booking = con.execute(
            """INSERT INTO bookings(booking_page_id,organisation_id,event_id,guest_name,guest_email,
               guest_notes,starts_at,ends_at,timezone,cancel_token_hash,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (page["id"], page["organisation_id"], cur.lastrowid, payload["guest_name"][:120],
             payload["guest_email"].lower()[:320], payload.get("guest_notes", "")[:2000],
             payload["starts_at"], payload["ends_at"], page["timezone"], token_hash, stamp))
        return int(booking.lastrowid), token


def cancel_booking(token: str) -> bool:
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT id,event_id FROM bookings WHERE cancel_token_hash=? AND status='confirmed'",
            (token_hash,)).fetchone()
        if not row:
            return False
        con.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (row["id"],))
        con.execute("DELETE FROM events WHERE id=?", (row["event_id"],))
        return True


init()
