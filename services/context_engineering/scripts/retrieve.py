from __future__ import annotations

import argparse

from ..libs.context_compression import ContextCompression
from ..libs.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve from graph (v2)")
    parser.add_argument("query")
    parser.add_argument("--session-id")
    parser.add_argument("--goal-id")
    parser.add_argument("-k", type=int, default=10)
    args = parser.parse_args()

    api = ContextCompression(get_settings())
    items = api.retrieve(args.query, session_id=args.session_id, goal_id=args.goal_id, k=args.k)
    for it in items:
        print(f"{it['id']}\t{it['score']}\t{it['text'][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
