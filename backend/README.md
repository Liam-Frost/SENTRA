# SENTRA Backend

Flask REST API for the SENTRA simulator and autonomy loop.

The backend owns:

- tick-based simulation (3 servers: `S1`, `S2`, `S3`)
- autonomy policy/controller
- realtime tick loop (server-driven ticking)
- SQLite event log (incidents/actions/faults/AI explanations)

## Setup

From `backend/`:

```bash
python -m venv .venv

# Windows
".venv/Scripts/python.exe" -m pip install -r requirements.txt

# macOS/Linux
".venv/bin/python" -m pip install -r requirements.txt
```

## Run (port 5000)

```bash
# Windows
".venv/Scripts/python.exe" -m flask --app app.main run --port 5000

# macOS/Linux
".venv/bin/python" -m flask --app app.main run --port 5000
```

## API

Base path: `/api`

- `GET /api/state`
- `POST /api/tick`
- `POST /api/fault`
- `GET /api/events`
- `POST /api/autonomy`
- `POST /api/reset`
- `GET /api/realtime`
- `POST /api/realtime`

Contract: `docs/03_API_CONTRACT.md`.

### Realtime mode

Enable/disable the server-driven tick loop:

```bash
curl -s http://localhost:5000/api/realtime
curl -s -X POST http://localhost:5000/api/realtime \
  -H "content-type: application/json" \
  -d '{"enabled": true, "hz": 5}'
```

## Simulation state

`GET /api/state` returns the world state and includes:

- `sim_version`: helps detect stale/old backend processes
- per server:
  - `status`: `booting`, `running`, `restarting`, `thermal_shutdown`, `off`
  - `cooling_level`: `0..1`

## Persistence

Operational data is stored in PostgreSQL when `SENTRA_DATABASE_URL` is set.
SQLite remains available as a local fallback.

- `SENTRA_DATABASE_URL` (optional): PostgreSQL connection string
- `SENTRA_DB_PATH` (optional): explicit SQLite path
- default SQLite path: `data/dev.sqlite3` (created on demand)

## Environment variables

- `SENTRA_SIM_SEED` (optional): deterministic simulation seed (default: `7`)
- `SENTRA_DATABASE_URL` (optional): PostgreSQL connection string (preferred)
- `SENTRA_DB_PATH` (optional): SQLite DB path fallback when `SENTRA_DATABASE_URL` is not set
- `SENTRA_AI_API_URL` / `SENTRA_AI_API_KEY` / `SENTRA_AI_MODEL` (optional): AI explanations
- `SENTRA_SIM_ENABLED` (optional): expose simulation endpoints when set to `true` (default: disabled)

## Tests

```bash
# Windows
".venv/Scripts/python.exe" -m pytest

# macOS/Linux
".venv/bin/python" -m pytest
```

## Notes

- World state is in-memory; multi-process deployments create one world per process.
- If `/api/realtime` returns 404, you're likely hitting an older backend process on port 5000.
