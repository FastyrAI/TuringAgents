import json

from libs.response_payloads import (
    build_acknowledgment_payload,
    build_progress_payload,
    build_stream_chunk_payload,
    build_stream_complete_payload,
    build_result_payload,
    build_error_payload,
)


def test_payload_builders_shapes():
    orig = {"message_id": "m1", "created_at": "2025-01-01T00:00:00Z"}

    ack = build_acknowledgment_payload(orig)
    assert ack == {
        "request_id": "m1",
        "type": "acknowledgment",
        "timestamp": "2025-01-01T00:00:00Z",
    }

    prog = build_progress_payload(orig, 40, "loading")
    assert prog == {
        "request_id": "m1",
        "type": "progress",
        "progress": 40,
        "status": "loading",
        "timestamp": "2025-01-01T00:00:00Z",
    }

    chunk = build_stream_chunk_payload(orig, "Hello", 0)
    assert chunk == {
        "request_id": "m1",
        "type": "stream_chunk",
        "chunk": "Hello",
        "chunk_index": 0,
        "timestamp": "2025-01-01T00:00:00Z",
    }

    complete = build_stream_complete_payload(orig, 2)
    assert complete == {
        "request_id": "m1",
        "type": "stream_complete",
        "total_chunks": 2,
        "timestamp": "2025-01-01T00:00:00Z",
    }

    result = build_result_payload(orig, {"ok": True})
    assert result == {
        "request_id": "m1",
        "type": "result",
        "result": {"ok": True},
        "timestamp": "2025-01-01T00:00:00Z",
    }

    err = build_error_payload(orig, RuntimeError("x"))
    assert err["request_id"] == "m1"
    assert err["type"] == "error"
    assert err["error"]["type"] == "RuntimeError"
    assert err["error"]["message"] == "x"


def test_error_payload_without_orig():
    err = build_error_payload(None, RuntimeError("oops"))
    assert err["request_id"] is None
    assert err["type"] == "error"
    assert err["error"]["type"] == "RuntimeError"
    assert err["error"]["message"] == "oops"

