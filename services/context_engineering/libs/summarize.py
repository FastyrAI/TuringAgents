from __future__ import annotations

import asyncio
from typing import Iterable, List, Sequence, Tuple

from .router import LLMRouter
from .metrics import SUMMARIZE_TOTAL, SUMMARIZE_LATENCY_SECONDS


SYSTEM_PREFIX = (
    "You are a precise summarization system. Use structured output: "
    "Executive Summary; Key Points; Decisions/Next Steps. Ensure citations like [S1], [S2]."
)


def _chunk(texts: Sequence[str], chunk_size: int = 2000) -> List[str]:
    chunks: List[str] = []
    current = ""
    for t in texts:
        if len(current) + len(t) + 1 > chunk_size and current:
            chunks.append(current)
            current = t
        else:
            current = (current + "\n" + t) if current else t
    if current:
        chunks.append(current)
    return chunks


def _build_prompt(texts: Sequence[str], must_include: Sequence[str] | None = None) -> str:
    numbered = "\n".join(f"[S{i+1}] {t}" for i, t in enumerate(texts))
    rules = (
        "- Must-include coverage >= 95% for given items.\n"
        "- Include numeric/date values faithfully.\n"
        "- Use citations [S#] for facts.\n"
    )
    include = "\n".join(f"- {x}" for x in (must_include or []))
    return f"{SYSTEM_PREFIX}\nRules:\n{rules}\nMust Include (if any):\n{include}\n\nContext:\n{numbered}\n\nSummarize now:"


def _is_bad_response(prompt: str, out: str) -> bool:
    if not out or out.strip() == "":
        return True
    # If model returns the same content (echo), treat as bad
    return out.strip().startswith(SYSTEM_PREFIX[:20]) or out.strip().startswith("You are a precise summarization system")


class Summarizer:
    def __init__(self, router: LLMRouter | None = None) -> None:
        self._router = router or LLMRouter()

    async def stuff(self, texts: Sequence[str], priority: str = "P1", must_include: Sequence[str] | None = None) -> str:
        prompt = _build_prompt(texts, must_include)
        with SUMMARIZE_LATENCY_SECONDS.labels(mode="stuff").time():
            SUMMARIZE_TOTAL.labels(mode="stuff").inc()
            out = await self._router.generate(prompt, priority=priority, context_len=len(prompt))
            if _is_bad_response(prompt, out):
                return await self.extractive(texts)
            return out

    async def refine(self, texts: Sequence[str], priority: str = "P1", must_include: Sequence[str] | None = None) -> str:
        chunks = _chunk(texts)
        running = ""
        for i, ch in enumerate(chunks):
            seed = [running] if running else []
            prompt = _build_prompt(seed + [ch], must_include)
            out = await self._router.generate(prompt, priority=priority, context_len=len(prompt))
            running = out if not _is_bad_response(prompt, out) else (await self.extractive([ch]))
        SUMMARIZE_TOTAL.labels(mode="refine").inc()
        return running

    async def map_reduce(self, texts: Sequence[str], priority: str = "P1", must_include: Sequence[str] | None = None) -> str:
        chunks = _chunk(texts)
        async def _map(ch: str) -> str:
            prompt = _build_prompt([ch], must_include)
            out = await self._router.generate(prompt, priority=priority, context_len=len(prompt))
            return out if not _is_bad_response(prompt, out) else await self.extractive([ch])
        with SUMMARIZE_LATENCY_SECONDS.labels(mode="map").time():
            mapped = await asyncio.gather(*[_map(ch) for ch in chunks])
        reduce_prompt = _build_prompt(mapped, must_include)
        out = await self._router.generate(reduce_prompt, priority=priority, context_len=len(reduce_prompt))
        if _is_bad_response(reduce_prompt, out):
            return await self.extractive(texts)
        SUMMARIZE_TOTAL.labels(mode="map_reduce").inc()
        return out

    async def recursive(self, texts: Sequence[str], priority: str = "P1", must_include: Sequence[str] | None = None) -> str:
        current: List[str] = list(texts)
        while len(current) > 8:
            current = [await self.map_reduce(current, priority=priority, must_include=must_include)]
        return await self.map_reduce(current, priority=priority, must_include=must_include)

    async def hybrid_map_refine(self, texts: Sequence[str], priority: str = "P1", must_include: Sequence[str] | None = None) -> str:
        mapped = await self.map_reduce(texts, priority=priority, must_include=must_include)
        refined = await self.refine([mapped], priority=priority, must_include=must_include)
        SUMMARIZE_TOTAL.labels(mode="hybrid").inc()
        return refined

    async def extractive(self, texts: Sequence[str], k: int = 12) -> str:
        # Simple extractive: pick top-k longest sentences as proxy
        sentences: List[str] = []
        for t in texts:
            for s in t.split(". "):
                s = s.strip()
                if s:
                    sentences.append(s)
        sentences.sort(key=lambda x: len(x), reverse=True)
        top = sentences[:k]
        bullet = "\n".join(f"- {s}" for s in top)
        SUMMARIZE_TOTAL.labels(mode="extractive").inc()
        return f"Executive Summary\n{bullet}"

    async def ensemble(self, texts: Sequence[str], priority: str = "P1") -> str:
        # Combine map-reduce and refine outputs
        mr, rf = await asyncio.gather(self.map_reduce(texts, priority=priority), self.refine(texts, priority=priority))
        merged = f"MapReduce Summary\n{mr}\n\nRefine Summary\n{rf}"
        SUMMARIZE_TOTAL.labels(mode="ensemble").inc()
        return merged

    async def streaming(self, texts_iter: Iterable[str], window: int = 5, step: int = 3) -> List[str]:
        # Produce periodic digests
        buffer: List[str] = []
        digests: List[str] = []
        for t in texts_iter:
            buffer.append(t)
            if len(buffer) >= window:
                digest = await self.map_reduce(buffer)
                digests.append(digest)
                buffer = buffer[step:]
        if buffer:
            digests.append(await self.map_reduce(buffer))
        SUMMARIZE_TOTAL.labels(mode="streaming").inc()
        return digests
