#!/usr/bin/env bash
set -euo pipefail

# Simple smoke test for LiteLLM proxy
# Requires: litellm running on localhost:4000 and LITELLM_MASTER_KEY set

HOST=${HOST:-"http://localhost:4000"}
KEY=${KEY:-"sk-dev-1234"}

echo "[smoke] Hitting health endpoint…"
curl -sSf "$HOST/health" | jq . >/dev/null || { echo "Health check failed"; exit 1; }

echo "[smoke] Sending chat completion request…"
curl -sSf \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "gpt-4o",
        "messages": [
          {"role": "user", "content": "Say hello"}
        ]
      }' \
  "$HOST/v1/chat/completions" | jq '.id, .choices[0].message.role' >/dev/null

echo "[smoke] OK"
