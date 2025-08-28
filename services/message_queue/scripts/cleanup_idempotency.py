"""Cleanup old idempotency keys to keep the table small.

Environment:
  - IDEMPOTENCY_TTL_DAYS (default 30)
  - SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""

import os
from datetime import datetime, timedelta, timezone

from supabase import create_client

from libs.config import Settings


def main() -> None:
    s = Settings()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Supabase not configured; skipping cleanup")
        return
    client = create_client(url, key)
    cutoff = datetime.now(timezone.utc) - timedelta(days=s.idempotency_ttl_days)
    # Delete old rows by created_at
    resp = client.table("idempotency_keys").delete().lt("created_at", cutoff.isoformat()).execute()
    deleted = len(resp.data or []) if hasattr(resp, "data") else 0
    print(f"Deleted {deleted} idempotency keys older than {cutoff.isoformat()}")


if __name__ == "__main__":
    main()


