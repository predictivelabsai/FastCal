"""Create the FastCal scheduling schema.

Revision ID: 20260809_0001
Revises:
"""

from __future__ import annotations

from sqlalchemy import text

from alembic import op
from fastcal.config import settings
from fastcal.db import models  # noqa: F401
from fastcal.db.base import Base

revision = "20260809_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{settings.DB_SCHEMA}"'))
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
