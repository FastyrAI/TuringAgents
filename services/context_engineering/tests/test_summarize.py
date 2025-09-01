import types
import pytest

from services.context_engineering.libs.summarize import Summarizer


class DummyRouter:
    async def generate(self, prompt: str, priority: str = "P1", context_len: int = 2000) -> str:
        return ""  # simulate empty LLM response to trigger fallback


def test_summarizer_fallback_to_extractive():
    texts = [
        "Order 12345 placed on 2024-07-01.",
        "Shipment ETA 3–5 days.",
        "Customer: Alice Johnson, NYC.",
    ]
    s = Summarizer(router=DummyRouter())
    out = __import__("asyncio").run(s.map_reduce(texts))
    assert "Executive Summary" in out
    assert "Order 12345" in out


def test_summarizer_refine_uses_router_output():
    class RouterOK:
        async def generate(self, prompt: str, priority: str = "P1", context_len: int = 2000) -> str:
            return "Summary: ok"
    s = Summarizer(router=RouterOK())
    out = __import__("asyncio").run(s.refine(["A", "B"]))
    assert "ok" in out


def test_summarizer_stuff_uses_fallback_when_bad():
    s = Summarizer(router=DummyRouter())
    out = __import__("asyncio").run(s.stuff(["A", "B"]))
    assert out.startswith("Executive Summary")


def test_summarizer_map_reduce_extractive_fallback():
    texts = [
        "Alpha one two three.",
        "Bravo four five six.",
        "Charlie seven eight nine.",
    ]
    s = Summarizer(router=DummyRouter())
    out = __import__("asyncio").run(s.map_reduce(texts))
    assert out.startswith("Executive Summary")


def test_summarizer_recursive_runs():
    # With dummy router, recursive should degrade to extractive output
    texts = [f"Sentence {i}." for i in range(30)]
    s = Summarizer(router=DummyRouter())
    out = __import__("asyncio").run(s.recursive(texts))
    assert "Executive Summary" in out


def test_summarizer_hybrid_runs():
    texts = ["Doc A content.", "Doc B content."]
    s = Summarizer(router=DummyRouter())
    out = __import__("asyncio").run(s.hybrid_map_refine(texts))
    assert "Executive Summary" in out or out != ""


def test_summarizer_ensemble_merges_two_methods():
    class RouterOK:
        async def generate(self, prompt: str, priority: str = "P1", context_len: int = 2000) -> str:
            return "S"
    s = Summarizer(router=RouterOK())
    out = __import__("asyncio").run(s.ensemble(["A", "B"]))
    assert "MapReduce Summary" in out and "Refine Summary" in out


def test_must_include_coverage_meets_threshold():
    # Arrange
    texts = [
        "Order 12345 placed on 2024-07-01 by Alice Johnson.",
        "Shipment ETA 3-5 days to NYC.",
    ]
    must_include = [
        "Order 12345",
        "2024-07-01",
        "Alice Johnson",
        "NYC",
        "3-5 days",
    ]

    class RouterIncludesAll:
        async def generate(self, prompt: str, priority: str = "P1", context_len: int = 2000) -> str:
            return (
                "Executive Summary; Key Points; Decisions/Next Steps. "
                "The order 12345 was placed on 2024-07-01 by Alice Johnson in NYC with ETA 3-5 days."
            )

    s = Summarizer(router=RouterIncludesAll())
    out = __import__("asyncio").run(s.stuff(texts, must_include=must_include))

    # Simple coverage metric: proportion of must-include items found as substrings
    out_low = out.lower()
    covered = sum(1 for item in must_include if item.lower() in out_low)
    coverage = covered / len(must_include)
    assert coverage >= 0.95


def test_deterministic_metrics_against_reference_summary():
    # Skip if core metric libs are unavailable
    rouge_mod = pytest.importorskip("rouge_score.rouge_scorer")
    nltk_meteor_mod = pytest.importorskip("nltk.translate.meteor_score")
    # BERTScore is optional; do not skip if missing
    try:
        import bert_score as bert_mod  # type: ignore
    except Exception:
        bert_mod = None

    # Arrange a tiny dataset with a known reference
    texts = [
        "Alice placed order 12345 on 2024-07-01.",
        "Shipment expected to NYC within 3-5 days.",
    ]
    reference_summary = (
        "Executive Summary: Alice placed order 12345 on 2024-07-01; "
        "shipment to NYC expected in 3-5 days."
    )

    class RouterReturnsReference:
        async def generate(self, prompt: str, priority: str = "P1", context_len: int = 2000) -> str:
            return reference_summary

    s = Summarizer(router=RouterReturnsReference())
    candidate = __import__("asyncio").run(s.stuff(texts))

    # ROUGE
    RougeScorer = rouge_mod.RougeScorer
    scorer = RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    r = scorer.score(reference_summary, candidate)
    assert r["rougeL"].fmeasure >= 0.95

    # METEOR (expects tokenized inputs)
    # METEOR (requires wordnet corpus; skip if missing). Force load to ensure availability.
    meteor_score = nltk_meteor_mod.meteor_score
    try:
        from nltk.corpus import wordnet
        _ = wordnet.synsets("dog")  # trigger resource load; raises LookupError if missing
    except Exception:
        # Attempt on-demand download if missing
        try:
            import nltk
            nltk.download("wordnet", quiet=True)
            nltk.download("omw-1.4", quiet=True)
            from nltk.corpus import wordnet as _wn
            _ = _wn.synsets("dog")
        except Exception:
            pytest.skip("nltk wordnet corpus not available")
    ref_tokens = reference_summary.split()
    cand_tokens = candidate.split()
    meteor = meteor_score([ref_tokens], cand_tokens)
    assert meteor >= 0.95

    # BERTScore (optional; only if lib and torch available)
    if bert_mod is not None:
        P, R, F1 = bert_mod.score([candidate], [reference_summary], model_type="bert-base-uncased")
        f1 = float(F1.mean().item())
        assert f1 >= 0.85


def test_extractive_direct():
    texts = [
        "Short sentence.",
        "This is a significantly longer sentence that should likely be selected.",
        "Another moderately long sentence appears here for selection consideration.",
    ]
    s = Summarizer(router=DummyRouter())
    k = 2
    out = __import__("asyncio").run(s.extractive(texts, k=k))
    assert out.startswith("Executive Summary")

    # Parse bullets and assert exact count == k
    lines = [ln for ln in out.split("\n") if ln.startswith("- ")]
    assert len(lines) == k

    # Recompute expected top-k longest sentences to assert membership
    sentences = []
    for t in texts:
        for snt in t.split(". "):
            snt = snt.strip()
            if snt:
                sentences.append(snt)
    sentences.sort(key=lambda x: len(x), reverse=True)
    expected_top = sentences[:k]
    bullet_texts = [ln[2:] for ln in lines]
    assert set(bullet_texts) == set(expected_top)


def test_streaming_direct():
    # Provide an iterator of messages and ensure digests are produced
    texts_iter = [f"message {i}" for i in range(10)]
    s = Summarizer(router=DummyRouter())
    digests = __import__("asyncio").run(s.streaming(texts_iter, window=4, step=2))
    # With window=4, step=2, n=10 → expected exactly 5 digests
    assert isinstance(digests, list) and len(digests) == 5
    for d in digests:
        assert d  # non-empty


def test_echo_fallback_triggers_extractive():
    class RouterEcho:
        async def generate(self, prompt: str, priority: str = "P1", context_len: int = 2000) -> str:
            return prompt  # echo the prompt → should be treated as bad and fallback

    s = Summarizer(router=RouterEcho())
    out = __import__("asyncio").run(s.stuff(["A", "B"]))
    assert out.startswith("Executive Summary")


def test_prompt_contains_must_include_items():
    captured = {"prompt": None}

    class RouterCapture:
        async def generate(self, prompt: str, priority: str = "P1", context_len: int = 2000) -> str:
            captured["prompt"] = prompt
            return "Summary"

    must_include = ["Alice Johnson", "Order 12345"]
    s = Summarizer(router=RouterCapture())
    __import__("asyncio").run(s.stuff(["Order 12345 placed by Alice Johnson."], must_include=must_include))
    prompt = captured["prompt"] or ""
    # Contract checks
    assert "You are a precise summarization system" in prompt
    assert "Rules:" in prompt and "Must Include (if any):" in prompt and "Context:" in prompt
    for item in must_include:
        assert f"- {item}" in prompt
    assert "[S1]" in prompt  # citation numbering present


def test_metrics_negative_candidate_low_scores():
    rouge_mod = pytest.importorskip("rouge_score.rouge_scorer")
    nltk_meteor_mod = pytest.importorskip("nltk.translate.meteor_score")

    reference_summary = (
        "Executive Summary: Alice placed order 12345 on 2024-07-01; shipment to NYC expected in 3-5 days."
    )
    good_candidate = reference_summary
    bad_candidate = "Completely unrelated summary about weather patterns with no overlap."

    RougeScorer = rouge_mod.RougeScorer
    scorer = RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    r_good = scorer.score(reference_summary, good_candidate)
    r_bad = scorer.score(reference_summary, bad_candidate)
    assert r_good["rougeL"].fmeasure >= 0.9
    assert r_bad["rougeL"].fmeasure <= 0.2
    assert (r_good["rougeL"].fmeasure - r_bad["rougeL"].fmeasure) >= 0.5

    meteor_score = nltk_meteor_mod.meteor_score
    try:
        from nltk.corpus import wordnet
        _ = wordnet.synsets("dog")  # trigger resource load; raises LookupError if missing
    except Exception:
        # Attempt on-demand download if missing
        try:
            import nltk
            nltk.download("wordnet", quiet=True)
            nltk.download("omw-1.4", quiet=True)
            from nltk.corpus import wordnet as _wn
            _ = _wn.synsets("dog")
        except Exception:
            pytest.skip("nltk wordnet corpus not available")
    ref_tokens = reference_summary.split()
    good_tokens = good_candidate.split()
    bad_tokens = bad_candidate.split()
    meteor_good = meteor_score([ref_tokens], good_tokens)
    meteor_bad = meteor_score([ref_tokens], bad_tokens)
    assert meteor_good >= 0.8
    assert meteor_bad <= 0.2
    assert (meteor_good - meteor_bad) >= 0.5
