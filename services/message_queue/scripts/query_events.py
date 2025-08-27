"""Query and print ordered lifecycle events for a message.

Usage:
  - Without args: infers last message_id from `.worker.log` (or last event)
  - With `--message-id`: queries that specific message

Outputs JSON with `message_id` and an ordered list of `{id, event_type, created_at}`.
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Optional

from supabase import create_client


def read_last_message_id_from_worker_log(log_path: Path) -> Optional[str]:
    """Return the last seen message_id from a worker log if present."""
    if not log_path.exists():
        return None
    pattern = re.compile(r"Worker received message ([a-f0-9-]+)")
    try:
        lines = log_path.read_text(errors="ignore").splitlines()
    except Exception:
        return None
    for line in reversed(lines):
        m = pattern.search(line)
        if m:
            return m.group(1)
    return None


def resolve_message_id(client, explicit_message_id: Optional[str]) -> Optional[str]:
    """Resolve message_id from CLI arg, worker log, or latest event row."""
    if explicit_message_id:
        return explicit_message_id
    mid = read_last_message_id_from_worker_log(Path(".worker.log"))
    if mid:
        return mid
    # Fallback to latest from message_events
    res = (
        client.table("message_events")
        .select("message_id,id")
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]["message_id"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Query ordered events for a message_id")
    parser.add_argument("--message-id", dest="message_id", default=None)
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    client = create_client(supabase_url, supabase_key)
    message_id = resolve_message_id(client, args.message_id)
    if not message_id:
        raise SystemExit("Could not determine message_id. Provide --message-id or ensure logs/events exist.")

    res = (
        client.table("message_events")
        .select("id,event_type,created_at")
        .eq("message_id", message_id)
        .order("created_at", desc=False)
        .order("id", desc=False)
        .execute()
    )
    print(json.dumps({"message_id": message_id, "events": res.data}, indent=2, default=str))


if __name__ == "__main__":
    main()


