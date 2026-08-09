# Repository Guidelines

## Project Structure & Module Organization

`app.py` is the Uvicorn compatibility entry point. Product code lives under
`fastcal/`: `auth/` owns Google and FastOffice identity, `db/` contains
SQLAlchemy models, `domain/` contains pure scheduling rules, `services/`
orchestrates bookings, `providers/` integrates Google Calendar, FastMeet, and
Postmark, `api/` exposes FastAPI, and `ui/` renders FastHTML. Alembic revisions
live in `alembic/`; tests live in `tests/`. Root `views.py`, `developer.py`, and
`seo.py` provide the anonymous public surface.

## Build, Test, and Development Commands

- `uv sync --extra dev` creates `.venv` and installs runtime/test tools.
- `docker compose up --build` starts PostgreSQL and FastCal on port 5021.
- `.venv/bin/alembic upgrade head` applies migrations to `DB_SCHEMA`.
- `.venv/bin/uvicorn app:app --reload --port 5021` runs locally.
- `.venv/bin/ruff check .` checks imports and Python style.
- `.venv/bin/pytest` runs database-independent tests.
- `FASTCAL_RUN_DB_TESTS=1 ... pytest tests/test_postgres_integration.py` runs
  transactional PostgreSQL coverage against the isolated `fast_cal` schema.

## Coding Style & Architecture

Use Python 3.12+, four-space indentation, type hints, `snake_case` functions,
`PascalCase` models, and `UPPER_SNAKE_CASE` settings. Keep route handlers thin.
Business rules belong in `domain/` or `services/`, SQL in repositories/services,
external HTTP in `providers/`, and markup in `ui/`. Format and lint with Ruff.

## Testing Guidelines

Name files `test_*.py` and tests `test_<behavior>`. Cover timezone and DST
boundaries, date overrides, buffers, external conflicts, tenant isolation,
round-robin fairness, idempotency, and concurrent slot reservation. Database
tests must roll back or use disposable records and must never alter other
PostgreSQL schemas.

## Commit & Pull Request Guidelines

Use concise imperative subjects such as `Add round-robin booking allocation`.
Keep commits focused. Pull requests should explain behavior, list verification
commands, call out migrations/environment changes, and include screenshots for
UI work.

## Security & Deployment

Never commit `.env`, database URLs, OAuth tokens, or cancellation links. Store
provider credentials encrypted. Scope every query by organisation. Production
uses `cal.fastsme.com`, PostgreSQL schema `fast_cal`, disabled development login,
and the sibling FastDevOps control plane.
