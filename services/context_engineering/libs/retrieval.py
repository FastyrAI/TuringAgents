from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from rank_bm25 import BM25Okapi  # type: ignore

from .models import RetrievedItem


@dataclass
class RankedList:
    name: str
    items: List[RetrievedItem]


def tokenize(text: str) -> List[str]:
    return text.lower().split()


def hash_embed(texts: Sequence[str], dim: int = 128) -> np.ndarray:
    vecs = np.zeros((len(texts), dim), dtype=np.float32)
    for i, t in enumerate(texts):
        for tok in tokenize(t):
            h = hash(tok) % dim
            vecs[i, h] += 1.0
    # l2 normalize
    norms = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9
    return vecs / norms


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.dot(a, b.T)


def mmr(diverse_candidates: Sequence[RetrievedItem], embeddings: np.ndarray, k: int, lambda_param: float = 0.7) -> List[RetrievedItem]:
    if len(diverse_candidates) == 0:
        return []
    k = min(k, len(diverse_candidates))
    selected: List[int] = []
    candidate_indices: List[int] = list(range(len(diverse_candidates)))

    sim_matrix = np.dot(embeddings, embeddings.T)
    query_vec = np.mean(embeddings, axis=0, keepdims=True)
    sim_to_query = np.dot(embeddings, query_vec.T).ravel()

    while len(selected) < k and candidate_indices:
        mmr_scores: List[Tuple[float, int]] = []
        for idx in candidate_indices:
            diversity = 0.0 if not selected else max(sim_matrix[idx, s] for s in selected)
            relevance = sim_to_query[idx]
            mmr_score = lambda_param * relevance - (1 - lambda_param) * diversity
            mmr_scores.append((float(mmr_score), idx))
        mmr_scores.sort(key=lambda x: x[0], reverse=True)
        best = mmr_scores[0][1]
        selected.append(best)
        candidate_indices.remove(best)

    return [diverse_candidates[i] for i in selected]


def rrf_fusion(ranked_lists: Sequence[RankedList], k: int = 10, k_rrf: int = 60) -> List[RetrievedItem]:
    scores: Dict[str, float] = {}
    texts: Dict[str, str] = {}
    for rl in ranked_lists:
        for rank, item in enumerate(rl.items, start=1):
            scores[item.id] = scores.get(item.id, 0.0) + 1.0 / (k_rrf + rank)
            texts[item.id] = item.text
    # Sort by accumulated scores
    fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
    return [RetrievedItem(id=_id, text=texts[_id], score=float(score)) for _id, score in fused]


class HybridRetriever:
    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._corpus_ids: List[str] = []
        self._corpus_texts: List[str] = []
        self._tokenized_corpus: List[List[str]] = []
        self._embeddings: np.ndarray | None = None

    def index(self, ids_and_texts: Iterable[Tuple[str, str]]) -> None:
        self._corpus_ids = []
        self._corpus_texts = []
        self._tokenized_corpus = []
        for _id, text in ids_and_texts:
            self._corpus_ids.append(_id)
            self._corpus_texts.append(text)
            self._tokenized_corpus.append(tokenize(text))
        if self._tokenized_corpus:
            self._bm25 = BM25Okapi(self._tokenized_corpus)
            self._embeddings = hash_embed(self._corpus_texts)
        else:
            self._bm25 = None
            self._embeddings = None

    def _bm25_rank(self, query: str, k: int) -> RankedList:
        if not self._bm25:
            return RankedList("bm25", [])
        toks = tokenize(query)
        scores = self._bm25.get_scores(toks)
        pairs = list(zip(self._corpus_ids, scores))
        pairs.sort(key=lambda x: x[1], reverse=True)
        items = [RetrievedItem(id=_id, text=self._corpus_texts[idx], score=float(score)) for idx, (_id, score) in enumerate(pairs[: max(k * 3, k)])]
        return RankedList("bm25", items)

    def _vector_rank(self, query: str, k: int) -> RankedList:
        if self._embeddings is None:
            return RankedList("vector", [])
        query_vec = hash_embed([query])
        sims = cosine_similarity(query_vec, self._embeddings).ravel()
        pairs = list(zip(self._corpus_ids, sims))
        pairs.sort(key=lambda x: x[1], reverse=True)
        items = [RetrievedItem(id=_id, text=self._corpus_texts[idx], score=float(score)) for idx, (_id, score) in enumerate(pairs[: max(k * 3, k)])]
        return RankedList("vector", items)

    def retrieve(self, query: str, k: int = 10, priors: Dict[str, float] | None = None) -> List[RetrievedItem]:
        priors_list: RankedList | None = None
        if priors:
            sorted_priors = sorted(priors.items(), key=lambda kv: kv[1], reverse=True)
            items = []
            for _id, score in sorted_priors[: k * 3]:
                if _id in self._corpus_ids:
                    idx = self._corpus_ids.index(_id)
                    items.append(RetrievedItem(id=_id, text=self._corpus_texts[idx], score=float(score)))
            priors_list = RankedList("priors", items)

        ranked_lists: List[RankedList] = [self._bm25_rank(query, k), self._vector_rank(query, k)]
        if priors_list:
            ranked_lists.append(priors_list)
        fused = rrf_fusion(ranked_lists, k=k)

        # Apply MMR diversity on top-k*3 items using hashed embeddings
        if not fused:
            return []
        candidate_texts = [it.text for it in fused]
        embs = hash_embed(candidate_texts, dim=128)
        diversified = mmr(fused, embs, k=k, lambda_param=0.7)
        return diversified
