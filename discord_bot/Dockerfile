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

# Drop privileges for runtime. The image uses root to install deps; switch
# to a non-root user once everything is in place.
RUN useradd --create-home --shell /bin/bash bot
USER bot

HEALTHCHECK --interval=60s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://backend:8000/healthz',timeout=3).status==200 else 1)" || exit 0

CMD ["python", "-m", "app.bot"]