FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY discord_bot/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY discord_bot/app /app/app

HEALTHCHECK --interval=60s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 0

CMD ["python", "-m", "app.bot"]