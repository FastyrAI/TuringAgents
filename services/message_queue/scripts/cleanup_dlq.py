"""
Purge old DLQ messages based on retention policy.

Environment:
  - DLQ_RETENTION_DAYS (default 90)
  - SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Usage:
  uv run python -m scripts.cleanup_dlq [--org-id ORG]
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from supabase import create_client

from libs.config import Settings
from libs.metrics import DLQ_PURGE_TOTAL


def purge(org_id: Optional[str] = None) -> int:
    """Delete DLQ rows older than retention days.

    If `org_id` is provided, only purge for that organization.
    Returns number of rows deleted (best-effort based on Supabase response).
    """
    s = Settings()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Supabase not configured; skipping DLQ purge")
        return 0
    client = create_client(url, key)
    cutoff = datetime.now(timezone.utc) - timedelta(days=s.dlq_retention_days)

    query = client.table("dlq_messages").delete().lt("dlq_timestamp", cutoff.isoformat())
    if org_id:
        query = query.eq("org_id", org_id)
    resp = query.execute()
    deleted = len(resp.data or []) if hasattr(resp, "data") else 0
    if org_id:
        DLQ_PURGE_TOTAL.labels(org_id=org_id).inc(deleted)
    print(
        f"Deleted {deleted} DLQ messages older than {cutoff.isoformat()}"
        + (f" for org={org_id}" if org_id else "")
    )
    return deleted


def main() -> None:
    """CLI entrypoint for purging DLQ messages beyond retention.

    Reads `DLQ_RETENTION_DAYS` via `Settings`, optionally filters by `--org-id`,
    and prints a summary of deleted rows. Intended to be run as a cron/job.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Cleanup old DLQ messages")
    parser.add_argument("--org-id", required=False, help="Purge only this org's DLQ rows")
    args = parser.parse_args()
    purge(args.org_id)


if __name__ == "__main__":
    main()

