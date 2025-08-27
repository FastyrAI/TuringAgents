"""Response payload builders for agent response queues.

These helpers centralize the JSON shapes for responses so producers,
workers, and coordinators remain consistent with the ADR.

How to use:
- Call the appropriate builder with the original request payload and
  any necessary fields, then publish the returned dict to the agent's
  response exchange via `libs.rabbit.publish_response`.

Examples:
>>> req = {"message_id": "m1", "created_at": "2025-01-01T00:00:00Z"}
>>> build_acknowledgment_payload(req)
{'request_id': 'm1', 'type': 'acknowledgment', 'timestamp': '2025-01-01T00:00:00Z'}
>>> build_progress_payload(req, 40, "loading")
{'request_id': 'm1', 'type': 'progress', 'progress': 40, 'status': 'loading', 'timestamp': '2025-01-01T00:00:00Z'}
>>> build_stream_chunk_payload(req, "hello", 0)
{'request_id': 'm1', 'type': 'stream_chunk', 'chunk': 'hello', 'chunk_index': 0, 'timestamp': '2025-01-01T00:00:00Z'}
>>> build_stream_complete_payload(req, 3)
{'request_id': 'm1', 'type': 'stream_complete', 'total_chunks': 3, 'timestamp': '2025-01-01T00:00:00Z'}
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


def _ts(orig: Mapping[str, Any]) -> Any:
    """Return timestamp for response payloads.

    Prefers the request's `created_at` to preserve traceability across systems.
    """
    return orig.get("created_at")


def build_acknowledgment_payload(orig: Mapping[str, Any]) -> dict[str, Any]:
    """Build an acknowledgment payload confirming message receipt/start.

    Why: Agents often need immediate feedback to update UI/UX that work has
    started. This mirrors the ADR's response taxonomy.

    Usage:
    - Publish as soon as the worker begins processing.

    Example:
    >>> build_acknowledgment_payload({"message_id": "m1", "created_at": "t"})
    {'request_id': 'm1', 'type': 'acknowledgment', 'timestamp': 't'}
    """
    return {
        "request_id": orig.get("message_id"),
        "type": "acknowledgment",
        "timestamp": _ts(orig),
    }


def build_progress_payload(orig: Mapping[str, Any], progress_percent: int, status: Optional[str] = None) -> dict[str, Any]:
    """Build a progress payload for long-running operations.

    Why: Allows UIs to render spinners/bars and for agents to coordinate.

    Usage:
    - Emit periodically during the task with a best-effort percentage.

    Example:
    >>> build_progress_payload({"message_id": "m1", "created_at": "t"}, 50, "halfway")
    {'request_id': 'm1', 'type': 'progress', 'progress': 50, 'status': 'halfway', 'timestamp': 't'}
    """
    payload: dict[str, Any] = {
        "request_id": orig.get("message_id"),
        "type": "progress",
        "progress": progress_percent,
        "timestamp": _ts(orig),
    }
    if status is not None:
        payload["status"] = status
    return payload


def build_stream_chunk_payload(orig: Mapping[str, Any], chunk: Any, chunk_index: int) -> dict[str, Any]:
    """Build a stream chunk payload with a piece of the result.

    Why: Supports low-latency streaming UIs per the ADR.

    Usage:
    - Emit one chunk per partial result.

    Example:
    >>> build_stream_chunk_payload({"message_id": "m1", "created_at": "t"}, "hi", 0)
    {'request_id': 'm1', 'type': 'stream_chunk', 'chunk': 'hi', 'chunk_index': 0, 'timestamp': 't'}
    """
    return {
        "request_id": orig.get("message_id"),
        "type": "stream_chunk",
        "chunk": chunk,
        "chunk_index": chunk_index,
        "timestamp": _ts(orig),
    }


def build_stream_complete_payload(orig: Mapping[str, Any], total_chunks: int, final_metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Build a stream completion payload to signal end of stream.

    Why: Lets coordinators/agents flush buffers and mark completion.

    Usage:
    - Emit once after the last chunk.

    Example:
    >>> build_stream_complete_payload({"message_id": "m1", "created_at": "t"}, 3)
    {'request_id': 'm1', 'type': 'stream_complete', 'total_chunks': 3, 'timestamp': 't'}
    """
    payload: dict[str, Any] = {
        "request_id": orig.get("message_id"),
        "type": "stream_complete",
        "total_chunks": int(total_chunks),
        "timestamp": _ts(orig),
    }
    if final_metadata:
        payload["metadata"] = final_metadata
    return payload


def build_result_payload(orig: Mapping[str, Any], result: Any) -> dict[str, Any]:
    """Build a non-streaming result payload for simple operations.

    Why: Many operations are atomic and do not require streaming.

    Example:
    >>> build_result_payload({"message_id": "m1", "created_at": "t"}, {"ok": True})
    {'request_id': 'm1', 'type': 'result', 'result': {'ok': True}, 'timestamp': 't'}
    """
    return {
        "request_id": orig.get("message_id"),
        "type": "result",
        "result": result,
        "timestamp": _ts(orig),
    }


def build_error_payload(orig: Mapping[str, Any] | None, exc: Exception) -> dict[str, Any]:
    """Build an error payload, tolerant to missing original payload.

    Example:
    >>> build_error_payload({"message_id": "m1"}, RuntimeError("x"))
    {'request_id': 'm1', 'type': 'error', 'error': {'type': 'RuntimeError', 'message': 'x'}}
    """
    return {
        "request_id": (orig or {}).get("message_id") if isinstance(orig, dict) else None,
        "type": "error",
        "error": {"type": exc.__class__.__name__, "message": str(exc)},
    }

