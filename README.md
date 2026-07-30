# FastCal

FastCal is the open, tenant-native calendar in the FastOffice suite. It
supports organisation calendars, events, time zones, attendees, reminders,
recurrence metadata, FastMeet links, and replay-protected FastOffice session
handoff.

Public booking pages provide Calendly/Cal.com-style external scheduling with
availability windows, notice and buffer rules, conflict-safe reservations,
guest details, and cancellation tokens. Optional Cal.com and Calendly v2
adapters consume runtime tokens; the local FastCal database remains the source
of truth.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
FASTCAL_DEV_LOGIN=true uvicorn app:app --port 5021
```
