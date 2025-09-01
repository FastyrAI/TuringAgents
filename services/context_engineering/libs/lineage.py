from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple

from .models import AuditEvent
from .metrics import MUST_INCLUDE_COVERAGE, NUMERIC_MISMATCH_RATE


AUDIT_LOG: List[AuditEvent] = []


def record_event(event_type: str, payload: Dict[str, Any]) -> str:
    evt = AuditEvent(event_type=event_type, payload=payload)
    AUDIT_LOG.append(evt)
    return evt.id


def must_include_coverage(summary_text: str, must_items: Sequence[str]) -> float:
    if not must_items:
        return 1.0
    hits = sum(1 for m in must_items if m.lower() in summary_text.lower())
    coverage = hits / max(1, len(must_items))
    MUST_INCLUDE_COVERAGE.observe(coverage)
    return coverage


def extract_numbers(text: str) -> List[str]:
    return re.findall(r"\b\d+[\d,\.]*\b", text)


def numeric_mismatch_rate(summary_text: str, sources: Sequence[str]) -> float:
    src_nums = set()
    for s in sources:
        src_nums.update(extract_numbers(s))
    if not src_nums:
        NUMERIC_MISMATCH_RATE.observe(0.0)
        return 0.0
    sum_nums = extract_numbers(summary_text)
    mismatches = [n for n in sum_nums if n not in src_nums]
    rate = len(mismatches) / max(1, len(sum_nums))
    NUMERIC_MISMATCH_RATE.observe(rate)
    return rate


def explain_citations(summary_text: str) -> Dict[str, List[str]]:
    # Very simple parser: sentence -> cited [S#]
    mapping: Dict[str, List[str]] = {}
    for sentence in summary_text.split(". "):
        sent = sentence.strip()
        if not sent:
            continue
        cites = re.findall(r"\[(S\d+)\]", sent)
        if cites:
            mapping[sent] = cites
    return mapping
