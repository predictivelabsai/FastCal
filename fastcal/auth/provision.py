"""Idempotent identity and organisation provisioning."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from fastcal.db.models import (
    AvailabilityRule,
    Membership,
    Organisation,
    Schedule,
    User,
)


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return clean[:64] or "workspace"


def provision_identity(
    session: Session,
    *,
    email: str,
    name: str,
    provider: str,
    provider_subject: str,
    organisation_id: str | None = None,
    organisation_name: str | None = None,
    role: str = "owner",
) -> tuple[User, Organisation]:
    email = email.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=name.strip() or email.split("@", 1)[0])
        session.add(user)
        session.flush()
    elif name and not user.name:
        user.name = name.strip()
    if provider == "google":
        user.google_subject = provider_subject
    elif provider == "fastoffice":
        user.fastoffice_subject = provider_subject

    org_id = organisation_id or f"personal:{user.id}"
    organisation = session.get(Organisation, org_id)
    if organisation is None:
        org_name = organisation_name or f"{user.name}'s workspace"
        base_slug = _slug(org_name)
        slug = base_slug
        counter = 1
        while session.scalar(select(Organisation.id).where(Organisation.slug == slug)):
            counter += 1
            slug = f"{base_slug[:58]}-{counter}"
        organisation = Organisation(id=org_id, name=org_name, slug=slug)
        session.add(organisation)
        session.flush()

    membership = session.scalar(
        select(Membership).where(
            Membership.organisation_id == organisation.id,
            Membership.user_id == user.id,
        )
    )
    if membership is None:
        membership = Membership(
            organisation_id=organisation.id,
            user_id=user.id,
            role=role,
            accepted=True,
        )
        session.add(membership)

    schedule = session.scalar(
        select(Schedule).where(
            Schedule.user_id == user.id, Schedule.is_default.is_(True)
        )
    )
    if schedule is None:
        schedule = Schedule(
            organisation_id=organisation.id,
            user_id=user.id,
            name="Working hours",
            timezone=user.timezone,
            is_default=True,
        )
        session.add(schedule)
        session.flush()
        for weekday in range(5):
            session.add(
                AvailabilityRule(
                    schedule_id=schedule.id,
                    weekday=weekday,
                    start_time=__import__("datetime").time(9, 0),
                    end_time=__import__("datetime").time(17, 0),
                )
            )
    session.flush()
    return user, organisation


def session_identity(
    user: User, organisation: Organisation, role: str
) -> dict[str, str]:
    return {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "org_id": organisation.id,
        "org_name": organisation.name,
        "role": role,
    }
