#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: $0 <panel_url> <agent_id> <node_id> [token]"
  exit 1
fi

PANEL_URL="$1"
AGENT_ID="$2"
NODE_ID="$3"
TOKEN="${4:-}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AGENT_DIR="$ROOT_DIR/agent"
VENV_DIR="$AGENT_DIR/.venv"

python -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$AGENT_DIR/requirements.txt"

cat > "$AGENT_DIR/.env" <<EOF
SENTRA_PANEL_URL=$PANEL_URL
SENTRA_AGENT_ID=$AGENT_ID
SENTRA_NODE_ID=$NODE_ID
SENTRA_AGENT_TOKEN=$TOKEN
SENTRA_AGENT_DRY_RUN=true
SENTRA_AGENT_INTERVAL=3
EOF

echo "Probe installed. Start with:"
echo "source \"$AGENT_DIR/.env\" && \"$VENV_DIR/bin/python\" \"$AGENT_DIR/probe_agent.py\""
