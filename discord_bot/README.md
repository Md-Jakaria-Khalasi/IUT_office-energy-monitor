# Office Energy Monitor — Discord bot

A Discord interface for the [Office Energy Monitor](../README.md) FastAPI
backend. The bot fetches all data from the backend at runtime — no values are
hardcoded — and surfaces a live dashboard, room breakdowns, recent activity,
active alerts, and a help listing via chat commands.

It also runs a background watcher that posts new backend alerts to a
configurable Discord channel automatically.

---

## Table of contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Discord application setup](#discord-application-setup)
- [Configuration (.env)](#configuration-env)
- [Run locally](#run-locally)
- [Run with Docker](#run-with-docker)
- [Commands](#commands)
- [Automatic alert notifications](#automatic-alert-notifications)
- [Architecture](#architecture)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Features

- **Live overview** of office energy use (devices, current draw, alerts,
  recent activity).
- **Per-room breakdowns** with device list and live wattage.
- **Usage leaderboard** combining top consuming rooms and the most recent
  activities.
- **Active alerts** listing, grouped by severity.
- **Automatic alert notifications** via a background poller — new alerts
  appear in your chosen channel without anyone running a command.
- **Resilient by design** — every command degrades gracefully when the
  backend is unreachable and surfaces a friendly error embed.
- **Zero hardcoded responses** — every embed is built from live backend
  data.

---

## Prerequisites

- Python **3.11+** (for local run)
- A running [Office Energy Monitor backend](../README.md) reachable from
  the bot's host
- A Discord account and a server you administer (for testing)

---

## Discord application setup

You need a bot user; the bot never needs to interact with users directly,
but it must be invited into a server.

1. Open the [Discord developer portal](https://discord.com/developers/applications)
   and click **New Application**. Give it any name (e.g. `Office Energy`).
2. In the left sidebar, go to **Bot** and click **Add Bot**.
3. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent** — required so the bot can read commands
     that begin with the configured prefix.
   - **Server Members Intent** — not strictly required, but recommended.
   - The **Bot** intent is on by default.
4. Click **Reset Token** and copy the new token. Treat this value as a
   password — paste it into `.env` as `DISCORD_TOKEN` (see below) and
   never commit it.
5. In the left sidebar, go to **OAuth2 → URL Generator**.
   - Scopes: `bot`, `applications.commands` (optional, only if you later
     add slash commands).
   - Bot permissions: at minimum
     - **Send Messages**
     - **Embed Links**
     - **Read Message History**
     - **Read Messages/View Channels** (always required)
6. Copy the generated URL, open it in your browser, pick your test server,
   and confirm the invite.

If the bot joins the server but never reacts to `!status`, the most common
cause is a missing **Message Content Intent** — go back to step 3.

---

## Configuration (.env)

All configuration is loaded from environment variables. Copy the example
file and edit it:

```bash
cp .env.example .env
```

### Required

| Variable         | Description                                                   |
| ---------------- | ------------------------------------------------------------- |
| `DISCORD_TOKEN`  | Bot token from the Discord developer portal.                  |
| `BACKEND_URL`    | Base URL of the FastAPI backend (no trailing slash).          |
| `COMMAND_PREFIX` | Prefix that triggers commands (default `!`).                  |

### Optional

| Variable                  | Default       | Description                                            |
| ------------------------- | ------------- | ------------------------------------------------------ |
| `BACKEND_API_PREFIX`      | `/api/v1`     | API prefix the backend exposes.                        |
| `REQUEST_TIMEOUT_SECONDS` | `10`          | Per-request HTTP timeout.                              |
| `ALERT_CHANNEL_ID`        | _(empty)_     | Numeric channel ID for automatic alert notifications. |
| `POLL_INTERVAL_SECONDS`   | `30`          | How often to poll `/alerts`.                           |
| `ALERT_POLL_LIMIT`        | `50`          | Max alerts fetched per poll cycle.                     |
| `LOG_LEVEL`               | `INFO`        | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.       |

If `ALERT_CHANNEL_ID` is left empty the watcher is disabled and the bot
only responds to commands. This is the right choice while you're testing
the bot in a sandbox channel.

---

## Run locally

```bash
cd discord_bot

# 1. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Make sure the backend is running and reachable
curl http://localhost:8000/api/v1/rooms/overview

# 4. Start the bot
python -m app.bot
```

On a successful connection you should see log lines similar to:

```
INFO  discord.client logging in using static token
INFO  app.bot logged in as Office Energy#1234 (id: ...)
INFO  app.bot alert watcher started (channel_id=..., interval=30s)
```

Type `!help` in any channel the bot can read.

---

## Run with Docker

The repository ships a `Dockerfile` inside `discord_bot/` and a
`docker-compose.yml` at the repo root. From the repo root:

```bash
# Make sure your .env is in place, then:
docker compose up --build discord_bot
```

Or build the image standalone:

```bash
cd discord_bot
docker build -t office-energy-bot .
docker run --env-file .env --name office-energy-bot office-energy-bot
```

The container's `HEALTHCHECK` calls the backend's `/api/v1/rooms/overview`
endpoint every 60 seconds, so `docker ps` will show whether the bot is
healthy.

---

## Commands

All commands use the configured prefix (default `!`). Each command sends a
rich embed (and updates it with a friendly error if anything goes wrong).

| Command         | Aliases                  | Description                                                    |
| --------------- | ------------------------ | -------------------------------------------------------------- |
| `!status`       | `!overview`, `!office`   | Office-wide totals: devices, current draw, active alerts, recent activity. |
| `!room <name>`  | `!roomstats`             | Per-room dashboard: wattage, device list, fuzzy name match.    |
| `!usage`        | `!activity`, `!recent`   | Top consuming rooms + most recent activity events.             |
| `!alerts`       | `!warnings`              | Active alerts grouped by severity.                             |
| `!help`         | `!h`, `!commands`        | Lists every command and a one-liner for each.                  |

### Examples

```
!status
!room Drawing Room
!room drawing              # fuzzy substring match
!usage
!alerts
!help
```

The room name in `!room` is matched case-insensitively as a substring,
so `!room drawing`, `!room Drawing`, and `!room Drawing Room` all hit the
same room.

---

## Automatic alert notifications

In addition to the on-demand `!alerts` command, the bot runs a background
task — `AlertWatcher` — that polls the backend `/alerts` endpoint every
`POLL_INTERVAL_SECONDS`. When new alerts appear, the bot posts a colored
embed (color reflects severity: info → warning → critical) into the
channel identified by `ALERT_CHANNEL_ID`.

- **First poll** backfills the bot's internal seen-set silently — only
  alerts that appear after startup are posted, so restarting the bot
  doesn't spam your channel.
- **Deduplication** is by alert ID, so the same alert posted on two
  consecutive polls is never re-posted.
- **Backend outages** are tolerated: a failed poll logs a warning and is
  retried on the next tick.

To enable notifications:

1. In Discord, right-click the channel where alerts should appear and
   choose **Copy Channel ID**. You need **Developer Mode** enabled
   (User Settings → Advanced).
2. Set `ALERT_CHANNEL_ID=<the-id>` in `.env` and restart the bot.

---

## Architecture

```
discord_bot/
├── app/
│   ├── bot.py                  # EnergyBot lifecycle + on_command_error
│   ├── config.py               # pydantic-settings + dotenv loader
│   ├── models.py               # Pydantic models mirroring backend
│   ├── api_client.py           # BackendClient (httpx) + typed errors
│   ├── embed_builder.py        # All embed construction
│   ├── cogs/
│   │   ├── status.py           # !status
│   │   ├── room.py             # !room <name>
│   │   ├── usage.py            # !usage
│   │   ├── alerts.py           # !alerts
│   │   └── help.py             # !help
│   └── services/
│       └── alert_watcher.py    # background /alerts poller
├── tests/
│   ├── conftest.py             # pytest fixtures + env shims
│   ├── test_api_client.py      # 12 tests
│   ├── test_commands.py        # 10 tests across 5 cogs
│   └── test_alert_watcher.py   # 7 tests for the watcher
├── pytest.ini                  # asyncio_mode=auto
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md                   # this file
```

**Design choices**

- **Clean separation.** Cogs know nothing about HTTP; they call
  `BackendClient` methods and pass models to `embed_builder`. Embed
  rendering is purely a function of data.
- **No hardcoded responses.** Every embed is built from live backend
  models. If the backend returns nothing, the embed says "no data".
- **Typed errors.** Every backend failure mode has a typed exception
  (`BackendConnectionError`, `BackendHTTPError`, `BackendNotFound`,
  `BackendValidationError`) so cogs can render appropriate messages.
- **Async throughout.** All backend I/O is `async`; the bot never blocks
  the event loop.
- **Self-contained tests.** Tests use `httpx.MockTransport` for the API
  client and tiny fakes for `discord.py` objects — no network and no
  Discord connection needed to run `pytest`.

---

## Testing

From the `discord_bot/` directory:

```bash
pip install -r requirements.txt
pytest
```

Expected: **29 tests pass** across three files:

- `tests/test_api_client.py` — 12 tests (every `BackendClient` method,
  every error path, context manager lifecycle)
- `tests/test_commands.py` — 10 tests (one per command plus edge cases:
  backend unreachable, fuzzy match, missing name, unknown room, empty
  data)
- `tests/test_alert_watcher.py` — 7 tests (backfill, dedup, disabled
  state, backend outage, channel resolution fallback)

To see coverage, install `pytest-cov` and run:

```bash
pytest --cov=app --cov-report=term-missing
```

---

## Troubleshooting

### `discord.errors.LoginFailure: Improper token has been passed.`

The `DISCORD_TOKEN` is wrong, missing, or has been reset. Generate a new
token in the Discord developer portal and update `.env`.

### Bot connects but `!status` returns an error embed

The bot reached Discord but couldn't reach the backend. Verify:

1. `BACKEND_URL` in `.env` points to a host the bot can actually reach
   (from inside Docker, `localhost` means the container — use
   `host.docker.internal` on Windows/macOS or the host's LAN IP on Linux).
2. The backend is running and `curl $BACKEND_URL/api/v1/rooms/overview`
   returns JSON.
3. The `BACKEND_API_PREFIX` matches the backend's actual prefix
   (`/api/v1` by default).

### Bot reacts to commands but no automatic alerts

Either `ALERT_CHANNEL_ID` is unset/empty, or the bot can't see the
target channel. Confirm:

- `ALERT_CHANNEL_ID` is a numeric ID (right-click → Copy Channel ID),
  not a name like `#alerts`.
- The bot has **View Channel** and **Send Messages** in that channel.
- The bot logs `alert watcher started` on startup — if it logs
  `alert watcher disabled`, the env var is missing.

### Tests fail with `ModuleNotFoundError: No module named 'app'`

Run `pytest` from the `discord_bot/` directory so the `app/` package is
on `sys.path`. The `tests/conftest.py` fixture adds it automatically,
but only when `pytest` is invoked from the project root.