#!/usr/bin/env bash
set -euo pipefail

# Lightweight load test using vegeta if available; otherwise a simple loop

HOST=${HOST:-"http://localhost:4000"}
KEY=${KEY:-"sk-dev-1234"}
RATE=${RATE:-50}      # requests per second
DURATION=${DURATION:-10s}

if command -v vegeta >/dev/null 2>&1; then
  echo "POST $HOST/v1/chat/completions" > /tmp/llm.targets
  echo '{"model":"gpt-4o","messages":[{"role":"user","content":"ping"}]}' > /tmp/llm.body
  vegeta attack -header "Authorization: Bearer $KEY" -header "Content-Type: application/json" -rate "$RATE" -duration "$DURATION" -body /tmp/llm.body -targets /tmp/llm.targets | vegeta report
else
  echo "[load] vegeta not found; running simple loop at ~$RATE rps for $DURATION"
  SECS=${DURATION%s}
  END=$(( $(date +%s) + SECS ))
  i=0
  while [ $(date +%s) -lt $END ]; do
    i=$((i+1))
    curl -s -o /dev/null -w "%{http_code}\n" \
      -H "Authorization: Bearer $KEY" \
      -H "Content-Type: application/json" \
      -d '{"model":"gpt-4o","messages":[{"role":"user","content":"ping"}]}' \
      "$HOST/v1/chat/completions" &
    sleep $(awk -v r=$RATE 'BEGIN{printf "%.4f", 1/r}')
  done
  wait
  echo "[load] Completed $i requests"
fi
