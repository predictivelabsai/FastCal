"""FastCal tenant-scoped integration API."""
from fastapi import Depends, FastAPI, Query

import db
from api_core import Principal, principal

api = FastAPI(
    title="FastCal API",
    version="1.0.0",
    description="Tenant-scoped calendars, events, booking pages and scheduling interoperability.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    servers=[{"url": "https://calendar.fastsme.com/api"}],
)


@api.get("/v1/health")
def health():
    return {"status": "ok", "product": "FastCal", "version": "1.0.0", "writes_enabled": True}


@api.get("/v1/events")
def list_events(q: str = Query(default=""), who: Principal = Depends(principal)):
    rows = db.events(who.organisation_id, q)
    return {"data": rows, "meta": {"total": len(rows), "limit": 100, "offset": 0}}


@api.get("/v1/events/{item_id}")
def get_event(item_id: int, who: Principal = Depends(principal)):
    rows = [row for row in db.events(who.organisation_id) if row["id"] == item_id]
    if not rows:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail={"code": "not_found"})
    return rows[0]


@api.post("/v1/events", status_code=201)
def create_event(payload: dict, who: Principal = Depends(principal)):
    identity = {"sub": who.subject, "org_id": who.organisation_id}
    event_id = db.create_event(identity, payload)
    return [row for row in db.events(who.organisation_id) if row["id"] == event_id][0]


@api.get("/v1/booking-pages")
def list_booking_pages(who: Principal = Depends(principal)):
    rows = db.booking_pages(who.organisation_id)
    return {"data": rows, "meta": {"total": len(rows), "limit": 100, "offset": 0}}
