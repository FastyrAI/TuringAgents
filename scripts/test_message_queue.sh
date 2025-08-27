#!/usr/bin/env bash
set -euo pipefail

# Run unit tests for the message queue service

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
SERVICE_DIR="$REPO_ROOT/services/message_queue"

cd "$SERVICE_DIR"

if python3 -m venv .venv 2>/dev/null; then
  source .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -e . pytest
  pytest -q
else
  echo "Falling back to system install (no venv available)" >&2
  python3 -m pip install --break-system-packages --upgrade pip
  python3 -m pip install --break-system-packages -e . pytest
  python3 -m pytest -q
fi

