from __future__ import annotations

from dataclasses import dataclass

from .config import OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY
from .metrics import ROUTER_DECISION_TOTAL


@dataclass
class RouteDecision:
    provider: str
    reason: str


class LLMRouter:
    def __init__(self) -> None:
        self._openai_available = bool(OPENAI_API_KEY)
        self._anthropic_available = bool(ANTHROPIC_API_KEY)
        self._gemini_available = bool(GEMINI_API_KEY)

    def decide(self, priority: str = "P1", context_len: int = 2000, require_json: bool = False) -> RouteDecision:
        # Prefer Gemini across the board if available
        if priority == "P0":
            if self._gemini_available:
                ROUTER_DECISION_TOTAL.labels(provider="gemini", reason="p0-default").inc()
                return RouteDecision("gemini", "p0-default")
            if self._openai_available:
                ROUTER_DECISION_TOTAL.labels(provider="openai", reason="p0-default").inc()
                return RouteDecision("openai", "p0-default")
            if self._anthropic_available:
                ROUTER_DECISION_TOTAL.labels(provider="anthropic", reason="p0-default").inc()
                return RouteDecision("anthropic", "p0-default")
            ROUTER_DECISION_TOTAL.labels(provider="extractive", reason="fallback").inc()
            return RouteDecision("extractive", "fallback")

        # Long context → Gemini first
        if context_len > 100_000 and self._gemini_available:
            ROUTER_DECISION_TOTAL.labels(provider="gemini", reason="long-context").inc()
            return RouteDecision("gemini", "long-context")

        # If JSON is required, still prefer Gemini if available
        if require_json:
            if self._gemini_available:
                ROUTER_DECISION_TOTAL.labels(provider="gemini", reason="json-mode").inc()
                return RouteDecision("gemini", "json-mode")
            if self._openai_available:
                ROUTER_DECISION_TOTAL.labels(provider="openai", reason="json-mode").inc()
                return RouteDecision("openai", "json-mode")

        # Balanced preference: Gemini → Anthropic → OpenAI
        if self._gemini_available:
            ROUTER_DECISION_TOTAL.labels(provider="gemini", reason="balanced").inc()
            return RouteDecision("gemini", "balanced")
        if self._anthropic_available:
            ROUTER_DECISION_TOTAL.labels(provider="anthropic", reason="balanced").inc()
            return RouteDecision("anthropic", "balanced")
        if self._openai_available:
            ROUTER_DECISION_TOTAL.labels(provider="openai", reason="balanced").inc()
            return RouteDecision("openai", "balanced")

        ROUTER_DECISION_TOTAL.labels(provider="extractive", reason="fallback").inc()
        return RouteDecision("extractive", "fallback")

    async def generate(self, prompt: str, priority: str = "P1", context_len: int = 2000) -> str:
        decision = self.decide(priority=priority, context_len=context_len)
        provider = decision.provider
        try:
            if provider == "gemini":
                return await self._call_gemini(prompt)
            if provider == "openai":
                return await self._call_openai(prompt)
            if provider == "anthropic":
                return await self._call_anthropic(prompt)
            return prompt
        except Exception as e:  # debug visibility for failures
            print(f"[router] provider={provider} error: {e}")
            return prompt

    async def _call_openai(self, prompt: str) -> str:
        from openai import AsyncOpenAI  # type: ignore

        client = AsyncOpenAI()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content or ""

    async def _call_anthropic(self, prompt: str) -> str:
        import anthropic  # type: ignore

        client = anthropic.AsyncAnthropic()
        msg = await client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=1024,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if getattr(block, "text", None))
        return text

    async def _call_gemini(self, prompt: str) -> str:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-pro")
        resp = await model.generate_content_async(prompt)
        # Robust extraction across SDK versions
        text = getattr(resp, "text", None)
        if text:
            return text
        try:
            candidates = getattr(resp, "candidates", None) or []
            if candidates:
                parts = getattr(candidates[0], "content", None)
                if parts and getattr(parts, "parts", None):
                    pieces = []
                    for p in parts.parts:
                        t = getattr(p, "text", None)
                        if t:
                            pieces.append(t)
                    if pieces:
                        return "".join(pieces)
        except Exception as e:
            print(f"[router] gemini response parse error: {e}")
        print("[router] gemini returned empty text")
        return ""
