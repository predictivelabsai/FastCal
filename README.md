# FastCal

FastCal is the open, tenant-native team calendar in the FastOffice suite. It
provides individual, collective, and weighted round-robin event types,
timezone-safe availability, Google Calendar conflict prevention, FastMeet
rooms, public booking links, cancellation, notifications, and a versioned API.

## Local development

The easiest local environment uses PostgreSQL through Docker Compose:

```bash
docker compose up --build
```

Open `http://localhost:5021/auth/dev`, then configure availability, teams, and
event types. To run directly:

```bash
uv sync --extra dev
export DB_URL=postgresql://fastcal:fastcal@localhost:5432/fastcal
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app:app --reload --port 5021
```

Production data is isolated in the PostgreSQL `fast_cal` schema. Use a
dedicated database role where possible; never commit connection URLs or OAuth
credentials.

## Verification

```bash
.venv/bin/ruff check .
.venv/bin/pytest
docker build -t fastcal:dev .
```

Database integration coverage is opt-in:

```bash
FASTCAL_RUN_DB_TESTS=1 DB_URL=... DB_SCHEMA=fast_cal .venv/bin/pytest \
  tests/test_postgres_integration.py
```

## Authentication and integrations

Google is the primary sign-in and calendar provider. Configure
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and the exact callback
`https://cal.fastsme.com/auth/google/callback`. FastOffice SSO uses
`FASTOFFICE_SSO_SECRET` and `/auth/suite/callback`. Postmark delivery requires
`POSTMARK_API_TOKEN`; FastMeet uses a short-lived FastOffice service ticket.

## Deployment

FastDevOps is the deployment source of truth:

```bash
python scripts/coolify.py validate
python scripts/coolify.py status
python scripts/coolify.py env --sync --yes
python scripts/coolify.py deploy --yes
```

The canonical production URL is `https://cal.fastsme.com`.
