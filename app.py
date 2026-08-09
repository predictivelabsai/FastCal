"""Compatibility entry point for Uvicorn and existing FastCal deployments."""

from __future__ import annotations

import uvicorn

from fastcal.config import settings
from fastcal.main import app

__all__ = ["app"]

if __name__ == "__main__":
    uvicorn.run(app, host=settings.FASTCAL_HOST, port=settings.FASTCAL_PORT)
