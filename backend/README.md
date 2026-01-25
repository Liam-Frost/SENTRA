# SENTRA Backend

The backend is a Flask REST API that serves the simulator state, executes ticks/actions,
and persists an event timeline to SQLite.

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

Endpoints live under `/api`:

- `GET /api/state`
- `POST /api/tick`
- `POST /api/fault`
- `GET /api/events`
- `POST /api/autonomy`
- `POST /api/reset`

See `docs/03_API_CONTRACT.md` for request/response shapes.

## Persistence

Events are stored in SQLite.

- `SENTRA_DB_PATH` (optional): explicit DB path
- default: `data/dev.sqlite3` (created on demand)

## AI explanations (optional)

If these environment variables are set, the backend will call an OpenAI-compatible
chat/completions endpoint for incident explanations:

- `SENTRA_AI_API_URL`
- `SENTRA_AI_API_KEY`
- `SENTRA_AI_MODEL`

If not set (or if the request fails), a deterministic fallback payload is used.

## Tests

```bash
# Windows
".venv/Scripts/python.exe" -m pytest

# macOS/Linux
".venv/bin/python" -m pytest
```

## Notes

- The simulator world state is in-memory; multi-process deployments will create one
  world per process.
