from datetime import datetime, timedelta

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTCAL_DB", str(tmp_path / "fastcal.sqlite"))
    monkeypatch.setenv("FASTCAL_DEV_LOGIN", "true")
    import importlib
    import db
    import app
    importlib.reload(db)
    importlib.reload(app)
    return TestClient(app.app)


def login(client):
    response = client.post("/auth/dev", data={"email": "kaljuvee@gmail.com"}, follow_redirects=True)
    assert response.status_code == 200


def test_public_landing_and_health(client):
    assert "Make time work for everyone" in client.get("/").text
    assert client.get("/health").json() == {"status": "ok", "product": "FastCal"}


def test_event_crud_is_authenticated(client):
    assert client.get("/events/new", follow_redirects=False).status_code == 303
    login(client)
    page = client.get("/events/new")
    assert "Schedule time" in page.text


def test_public_booking_creates_tenant_event(client):
    login(client)
    response = client.post("/booking-pages", data={
        "title": "Discovery call", "duration_minutes": "30", "available_from": "00:00",
        "available_to": "23:59", "timezone": "Europe/Tallinn", "minimum_notice_hours": "0",
        "buffer_minutes": "0", "location": "FastMeet",
    }, follow_redirects=True)
    assert "Discovery call" in response.text
    slug = response.url.path.rsplit("/", 1)[-1]
    import db
    page = db.booking_page(slug)
    import app
    slots = app.available_slots(page)
    assert slots
    slot = slots[0]
    booked = client.post(f"/book/{slug}", data={
        "guest_name": "Outside Guest", "guest_email": "guest@example.com",
        "starts_at": slot["starts_at"], "ends_at": slot["ends_at"], "guest_notes": "Planning",
    }, follow_redirects=True)
    assert "confirmed" in booked.text
    assert any("Outside Guest" in row["title"] for row in db.events(page["organisation_id"]))


def test_booking_page_is_tenant_scoped(client):
    login(client)
    import db
    who = {"sub": "other", "email": "other@example.com", "name": "Other",
           "org_id": "other-org", "org_name": "Other Org", "role": "owner"}
    db.provision(who)
    with db.connect() as con:
        first_org = con.execute("SELECT organisation_id FROM calendars WHERE organisation_id='dev'").fetchone()
    with pytest.raises(ValueError):
        db.create_event(who, {
            "calendar_id": 1, "title": "Cross-tenant", "starts_at": "2026-08-01T10:00",
            "ends_at": "2026-08-01T10:30",
        })
