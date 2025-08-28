#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$REPO_ROOT"

echo "[1/3] Building message_queue image..."
docker compose build message_queue | cat

echo "[2/3] Running tests in ephemeral container..."
docker compose run --rm message_queue bash -lc \
  ". .venv/bin/activate && cd /app && uv pip install -q pytest pytest-asyncio && python -m pytest -q" | cat

echo "[3/3] Done."


