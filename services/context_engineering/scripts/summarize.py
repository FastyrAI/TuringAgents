from __future__ import annotations

import argparse
import asyncio

from ..libs.api import ContextEngineeringAPI
from ..libs.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize session (v2)")
    parser.add_argument("session_id")
    parser.add_argument("--algorithm", default="map_reduce")
    args = parser.parse_args()

    api = ContextEngineeringAPI(get_settings())
    rows = api.graph.get_session_texts(args.session_id)
    texts = [t for _id, t, _ts in rows]
    out = asyncio.run(api.summarize(texts, session_id=args.session_id, algorithm=args.algorithm))
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
