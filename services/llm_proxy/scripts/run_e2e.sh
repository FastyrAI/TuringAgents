#!/usr/bin/env bash
set -euo pipefail

# Run llm_proxy E2E tests

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/../../.. && pwd)
pushd "$ROOT_DIR" >/dev/null

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to run E2E tests (for compose up)." >&2
  exit 1
fi

echo "[e2e] Starting LiteLLM via docker compose..."
docker compose -f docker-compose.yml -f services/llm_proxy/compose/docker-compose.override.yml --env-file services/llm_proxy/.env up -d

echo "[e2e] Installing test dependencies..."
python -m pip install -e services/llm_proxy[test]

echo "[e2e] Running pytest..."
pytest -q services/llm_proxy/tests/e2e

echo "[e2e] Done"
