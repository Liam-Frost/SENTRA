#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

python_from_venv() {
  if [ -x "$BACKEND_DIR/.venv/Scripts/python.exe" ]; then
    echo "$BACKEND_DIR/.venv/Scripts/python.exe"
    return
  fi
  if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
    echo "$BACKEND_DIR/.venv/bin/python"
    return
  fi
  echo ""
}

ensure_backend_venv() {
  if [ ! -d "$BACKEND_DIR/.venv" ]; then
    (cd "$BACKEND_DIR" && python -m venv .venv)
  fi

  local py
  py="$(python_from_venv)"
  if [ -z "$py" ]; then
    echo "ERROR: could not find backend venv python" >&2
    exit 1
  fi

  (cd "$BACKEND_DIR" && "$py" -m pip install -r requirements.txt)
}

start_backend() {
  ensure_backend_venv

  local py
  py="$(python_from_venv)"

  echo "[backend] http://localhost:5000"
  (cd "$BACKEND_DIR" && FLASK_DEBUG=1 "$py" -m flask --app app.main run --port 5000)
}

start_frontend() {
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    (cd "$FRONTEND_DIR" && npm install)
  fi

  echo "[frontend] http://localhost:5173"
  (cd "$FRONTEND_DIR" && npm run dev)
}

cleanup() {
  echo "Shutting down..."
  kill 0 || true
}

trap cleanup EXIT INT TERM

start_backend &
start_frontend
