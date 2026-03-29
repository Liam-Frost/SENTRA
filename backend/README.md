# SENTRA Backend

Flask API for the SENTRA control plane.

The backend currently serves four major responsibilities:

- fleet registration, heartbeat, and metrics ingestion
- operation template CRUD and execution orchestration
- project and load balancer management
- load balancer policy CRUD and apply workflow

## Setup

From `backend/`:

```bash
python -m venv .venv

# Windows
".venv/Scripts/python.exe" -m pip install -r requirements.txt

# macOS/Linux
".venv/bin/python" -m pip install -r requirements.txt
```

## Run

```bash
# Windows
".venv/Scripts/python.exe" -m flask --app app.main run --port 5000

# macOS/Linux
".venv/bin/python" -m flask --app app.main run --port 5000
```

## Persistence

Preferred:

- `SENTRA_DATABASE_URL=postgresql://...`

Fallback:

- `SENTRA_DB_PATH=...`

If `SENTRA_DATABASE_URL` is not set, the backend uses local SQLite storage.

## Environment variables

- `SENTRA_DATABASE_URL`: PostgreSQL connection string
- `SENTRA_DB_PATH`: SQLite fallback path
- `SENTRA_SIM_ENABLED`: expose simulator/debug endpoints when `true`
- `SENTRA_AI_API_URL` / `SENTRA_AI_API_KEY` / `SENTRA_AI_MODEL`: optional AI integration

Simulation-specific settings still exist for debug flows, but they are not part of
the main product path.

## Main API areas

Control plane:

- `GET /api/capabilities`
- `GET /api/dashboard`
- `GET /api/nodes`
- `GET /api/projects`
- `GET /api/lb-policies`
- `GET /api/operation-templates`

Agent:

- `POST /api/agents/register`
- `POST /api/agents/heartbeat`
- `POST /api/agents/metrics`
- `GET /api/agents/commands/next`
- `POST /api/agents/commands/:run_id/logs`
- `POST /api/agents/commands/:run_id/result`

Legacy/debug:

- `GET /api/state`
- `POST /api/tick`
- `POST /api/fault`
- `POST /api/reset`
- `GET/POST /api/realtime`

Canonical contract: `docs/03_API_CONTRACT.md`

## Tests

```bash
# Windows
".venv/Scripts/python.exe" -m pytest

# macOS/Linux
".venv/bin/python" -m pytest
```

## Notes

- operation template executions are stored through the existing `operations` / `operation_runs`
  pipeline, with `action_type = template_execution`
- load balancer policy apply currently creates execution jobs using generated shell-step payloads
- simulation support remains in the backend for demo and debug purposes only
