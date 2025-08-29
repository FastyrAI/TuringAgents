# Context Engineering v2 (MVP)

Implements the ADR in `docs/context_engineering_v2.md`:
- Graph memory on Neo4j
- Hybrid retrieval (BM25 + vector hash + RRF + MMR)
- Summarization strategies (Stuff/Refine/MapReduce/Recursive/Hybrid/Extractive/Ensemble/Streaming)
- Multi-LLM router with fallback
- Lineage/Verification hooks

## Quickstart

1. Set environment variables:
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
# Optional:
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
```

2. Ingest:
```
python -m services.context_engineering_v2.scripts.main ingest SESSION_ID "Some text"
```

3. Retrieve:
```
python -m services.context_engineering_v2.scripts.main retrieve "query" --session-id SESSION_ID -k 5
```

4. Summarize:
```
python -m services.context_engineering_v2.scripts.main summarize SESSION_ID --algorithm map_reduce
```
