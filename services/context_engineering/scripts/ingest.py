from __future__ import annotations

import argparse

from ..libs.context_compression import ContextCompression
from ..libs.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest text into graph (v2)")
    parser.add_argument("session_id")
    parser.add_argument("text")
    parser.add_argument("--scope", default="session")
    parser.add_argument("--org-id", dest="org_id")
    parser.add_argument("--goal-id", dest="goal_id")
    args = parser.parse_args()

    api = ContextCompression(get_settings())
    _id = api.ingest(args.text, session_id=args.session_id, scope=args.scope, org_id=args.org_id, goal_id=args.goal_id)
    print(_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
