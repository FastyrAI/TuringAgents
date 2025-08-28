from __future__ import annotations

import argparse
import asyncio
import sys

from .libs.context_compression import ContextCompression
from .libs.config import get_settings
from .libs.metrics import start_metrics_server, HEALTH_GAUGE


def cmd_ingest(api: ContextCompression, args: argparse.Namespace) -> None:
    _id = api.ingest(args.text, session_id=args.session_id, scope=args.scope, org_id=args.org_id, goal_id=args.goal_id)
    print(_id)


def cmd_retrieve(api: ContextCompression, args: argparse.Namespace) -> None:
    items = api.retrieve(args.query, session_id=args.session_id, goal_id=args.goal_id, k=args.k)
    for it in items:
        print(f"{it['id']}\t{it['score']}\t{it['text'][:120]}")


def cmd_summarize(api: ContextCompression, args: argparse.Namespace) -> None:
    rows = api.graph.get_session_texts(args.session_id)
    texts = [t for _id, t, _ts in rows]
    out = asyncio.run(api.summarize(texts, session_id=args.session_id, algorithm=args.algorithm))
    print(out)


def cmd_snapshot(api: ContextCompression, args: argparse.Namespace) -> None:
    out = asyncio.run(api.snapshot(args.session_id))
    print(out)


def cmd_verify(api: ContextCompression, args: argparse.Namespace) -> None:
    rows = api.graph.get_session_texts(args.session_id)
    texts = [t for _id, t, _ts in rows]
    res = api.verify(args.summary, texts)
    print(res)


def cmd_expire(api: ContextCompression, args: argparse.Namespace) -> None:
    deleted = api.graph.expire_ephemeral()
    print({"deleted": deleted})


def cmd_pipeline(api: ContextCompression, args: argparse.Namespace) -> None:
    # Ingest provided texts (can pass multiple --text)
    for t in (args.text or []):
        _id = api.ingest(t, session_id=args.session_id, scope=args.scope, org_id=args.org_id, goal_id=args.goal_id)
        print({"ingested_id": _id})
    # Retrieve
    items = []
    if args.query:
        items = api.retrieve(args.query, session_id=args.session_id, goal_id=args.goal_id, k=args.k)
        print({"retrieved": len(items)})
        for it in items:
            print(f"{it['id']}\t{it['score']}\t{it['text'][:120]}")
    # Summarize session
    out = asyncio.run(api.summarize([it["text"] for it in items] if items else [t for _id, t, _ts in api.graph.get_session_texts(args.session_id)], session_id=args.session_id, algorithm=args.algorithm))
    print("\n=== SUMMARY ===\n" + out)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description="Context Engineering v2 Manager")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("session_id")
    p_ingest.add_argument("text")
    p_ingest.add_argument("--scope", default="session")
    p_ingest.add_argument("--org-id", dest="org_id")
    p_ingest.add_argument("--goal-id", dest="goal_id")

    p_retrieve = sub.add_parser("retrieve")
    p_retrieve.add_argument("query")
    p_retrieve.add_argument("--session-id")
    p_retrieve.add_argument("--goal-id")
    p_retrieve.add_argument("-k", type=int, default=10)

    p_summarize = sub.add_parser("summarize")
    p_summarize.add_argument("session_id")
    p_summarize.add_argument("--algorithm", default="map_reduce")

    p_snapshot = sub.add_parser("snapshot")
    p_snapshot.add_argument("session_id")

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("session_id")
    p_verify.add_argument("summary")

    p_expire = sub.add_parser("expire")

    p_pipeline = sub.add_parser("pipeline")
    p_pipeline.add_argument("session_id")
    p_pipeline.add_argument("--text", action="append", help="Repeatable: texts to ingest before run")
    p_pipeline.add_argument("--scope", default="session")
    p_pipeline.add_argument("--org-id", dest="org_id")
    p_pipeline.add_argument("--goal-id", dest="goal_id")
    p_pipeline.add_argument("--query")
    p_pipeline.add_argument("-k", type=int, default=10)
    p_pipeline.add_argument("--algorithm", default="map_reduce")

    args = parser.parse_args(argv)

    settings = get_settings()
    start_metrics_server(settings.metrics_port)
    HEALTH_GAUGE.set(1)

    api = ContextCompression(settings)

    if args.cmd == "ingest":
        cmd_ingest(api, args)
    elif args.cmd == "retrieve":
        cmd_retrieve(api, args)
    elif args.cmd == "summarize":
        cmd_summarize(api, args)
    elif args.cmd == "snapshot":
        cmd_snapshot(api, args)
    elif args.cmd == "verify":
        cmd_verify(api, args)
    elif args.cmd == "expire":
        cmd_expire(api, args)
    elif args.cmd == "pipeline":
        cmd_pipeline(api, args)
    else:
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
