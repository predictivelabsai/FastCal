FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FASTCAL_ENV=production \
    FASTCAL_HOST=0.0.0.0 \
    FASTCAL_PORT=5021 \
    DB_SCHEMA=fast_cal

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system fastcal \
    && adduser --system --ingroup fastcal fastcal

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R fastcal:fastcal /app
USER fastcal

EXPOSE 5021
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail http://127.0.0.1:5021/health || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn app:app --host 0.0.0.0 --port 5021"]
