from __future__ import annotations

import asyncio
from typing import Dict, List, Sequence

from .config import Settings, get_settings
from .graph import GraphClient
from .models import Message, Summary
from .retrieval import HybridRetriever
from .router import LLMRouter
from .summarize import Summarizer
from .lineage import record_event, must_include_coverage, numeric_mismatch_rate, explain_citations
from .metrics import INGEST_TOTAL, RETRIEVE_TOTAL, SUMMARIZE_TOTAL


def _extract_entities_naive(text: str) -> List[str]:
    # Very naive heuristic: capitalized tokens as entities
    ents: List[str] = []
    for tok in text.split():
        if len(tok) > 2 and tok[0].isupper():
            ents.append(tok.strip(",.!?:;()[]{}"))
    return list({e for e in ents if e})


class ContextCompression:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.graph = GraphClient(self.settings.graph_uri, self.settings.graph_user, self.settings.graph_password)
        self.router = LLMRouter()
        self.summarizer = Summarizer(self.router)

    # --- Ingest ---
    def ingest(self, input_text: str, session_id: str, scope: str = "session", org_id: str | None = None, goal_id: str | None = None, metadata: dict | None = None) -> str:
        msg = Message(org_id=org_id, session_id=session_id, goal_id=goal_id, scope=scope, text=input_text, metadata=metadata)
        with INGEST_TOTAL.labels(type="message", result="attempt").count_exceptions():
            self.graph.upsert_message(msg)
            ents = _extract_entities_naive(input_text)
            self.graph.link_message_mentions(msg.id, ents)
            record_event("ingest", {"message_id": msg.id, "ents": ents})
        INGEST_TOTAL.labels(type="message", result="success").inc()
        return msg.id

    # --- Retrieve ---
    def retrieve(self, query: str, session_id: str | None = None, goal_id: str | None = None, k: int = 10) -> List[Dict[str, str]]:
        RETRIEVE_TOTAL.labels(strategy="hybrid").inc()
        if session_id:
            rows = self.graph.get_session_texts(session_id)
            priors = {mid: 1.0 for mid, _t, _ts in rows[-20:]}  # boost recency
        elif goal_id:
            rows = self.graph.get_goal_texts(goal_id)
            priors = {mid: 1.0 for mid, _t, _ts in rows[-20:]}
        else:
            rows = []
            priors = {}
        retriever = HybridRetriever()
        retriever.index((mid, txt) for mid, txt, _ts in rows)
        items = retriever.retrieve(query, k=k, priors=priors)
        return [{"id": it.id, "text": it.text, "score": f"{it.score:.4f}"} for it in items]

    # --- Summarize ---
    async def summarize(self, node_texts: Sequence[str], session_id: str, algorithm: str = "map_reduce", priority: str = "P1", must_include: Sequence[str] | None = None) -> str:
        if algorithm == "stuff":
            text = await self.summarizer.stuff(node_texts, priority=priority, must_include=must_include)
        elif algorithm == "refine":
            text = await self.summarizer.refine(node_texts, priority=priority, must_include=must_include)
        elif algorithm == "map_reduce":
            text = await self.summarizer.map_reduce(node_texts, priority=priority, must_include=must_include)
        elif algorithm == "recursive":
            text = await self.summarizer.recursive(node_texts, priority=priority, must_include=must_include)
        elif algorithm == "hybrid_map_refine":
            text = await self.summarizer.hybrid_map_refine(node_texts, priority=priority, must_include=must_include)
        elif algorithm == "extractive":
            text = await self.summarizer.extractive(node_texts)
        elif algorithm == "ensemble":
            text = await self.summarizer.ensemble(node_texts, priority=priority)
        else:
            text = await self.summarizer.map_reduce(node_texts, priority=priority, must_include=must_include)
        SUMMARIZE_TOTAL.labels(mode=algorithm).inc()
        # Verification
        coverage = must_include_coverage(text, must_include or [])
        mismatch = numeric_mismatch_rate(text, node_texts)
        record_event("summarize", {"session_id": session_id, "algorithm": algorithm, "coverage": coverage, "numeric_mismatch": mismatch})
        # Persist summary
        sum_node = Summary(session_id=session_id, text=text, scope="session")
        self.graph.create_summary(sum_node)
        return text

    # --- Snapshot ---
    async def snapshot(self, session_id: str) -> str:
        rows = self.graph.get_session_texts(session_id)
        texts = [t for _id, t, _ts in rows]
        return await self.summarize(texts, session_id=session_id, algorithm="hybrid_map_refine")

    # --- Verify & Explain ---
    def verify(self, summary_text: str, source_texts: Sequence[str], must_include: Sequence[str] | None = None) -> Dict[str, float]:
        return {
            "coverage": must_include_coverage(summary_text, must_include or []),
            "numeric_mismatch": numeric_mismatch_rate(summary_text, source_texts),
        }

    def explain(self, summary_text: str) -> Dict[str, List[str]]:
        return explain_citations(summary_text)

    # --- Conflict Resolution ---
    def resolve_conflict(self, text_a: str, text_b: str) -> Dict[str, str]:
        # Simple heuristic: prefer longer; record decision
        winner = text_a if len(text_a) >= len(text_b) else text_b
        loser = text_b if winner is text_a else text_a
        record_event("conflict_resolved", {"winner_len": len(winner), "loser_len": len(loser)})
        return {"winner": winner, "loser": loser}


