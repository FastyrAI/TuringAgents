from libs.retry import next_delay_ms, demote_priority, decide_retry
from libs.backpressure import BackpressureConfig, decide_throttle
from libs.validation import validate_message
import pytest


def test_next_delay_ms_bounds():
    delays = [1, 2, 4]
    assert next_delay_ms(0, delays) == 1
    assert next_delay_ms(1, delays) == 2
    assert next_delay_ms(2, delays) == 4
    assert next_delay_ms(3, delays) == 4  # clamp to last


def test_decide_throttle_modes():
    cfg = BackpressureConfig(scale_threshold=100, light_throttle_threshold=500, heavy_throttle_threshold=1000, emergency_threshold=5000)
    assert decide_throttle(50, cfg) == "none"
    assert decide_throttle(600, cfg) == "light"
    assert decide_throttle(1500, cfg) == "heavy"
    assert decide_throttle(6000, cfg) == "emergency"


def test_validate_message_ok():
    msg = {
        "message_id": "m1",
        "version": "1.0.0",
        "org_id": "org",
        "type": "agent_message",
        "priority": 2,
        "created_by": {"type": "system", "id": "x"},
        "created_at": "2025-01-01T00:00:00Z",
    }
    validate_message(msg)  # no exception


def test_validate_message_invalid_priority():
    msg = {
        "message_id": "m1",
        "version": "1.0.0",
        "org_id": "org",
        "type": "agent_message",
        "priority": 10,
        "created_by": {"type": "system", "id": "x"},
        "created_at": "2025-01-01T00:00:00Z",
    }
    with pytest.raises(Exception):
        validate_message(msg)


def test_demote_priority_bounds():
    assert demote_priority(0) == 1
    assert demote_priority(1) == 2
    assert demote_priority(2) == 3
    assert demote_priority(3) == 3


def test_decide_retry_exponential_and_demotion():
    msg = {
        "message_id": "m2",
        "version": "1.0.0",
        "org_id": "org",
        "type": "model_call",
        "priority": 1,
        "created_by": {"type": "system", "id": "x"},
        "created_at": "2025-01-01T00:00:00Z",
        "retry_count": 0,
    }
    d = decide_retry(msg, Exception("boom"), delays=[100, 200, 400])
    assert d.should_retry is True
    assert d.delay_ms == 100
    assert d.next_priority == 2
    assert d.next_retry_count == 1


def test_decide_retry_no_retry_on_validation_error():
    class FakeValidationError(Exception):
        pass
    # Match by name to simulate pydantic ValidationError without importing
    FakeValidationError.__name__ = "ValidationError"
    msg = {
        "message_id": "m3",
        "version": "1.0.0",
        "org_id": "org",
        "type": "tool_call",
        "priority": 0,
        "created_by": {"type": "system", "id": "x"},
        "created_at": "2025-01-01T00:00:00Z",
        "retry_count": 0,
    }
    d = decide_retry(msg, FakeValidationError("bad input"))
    assert d.should_retry is False
    assert d.next_priority == 0
    assert d.next_retry_count == 0


def test_decide_retry_rate_limit_wait_and_demotion():
    class RateLimitError(Exception):
        pass
    msg = {
        "message_id": "m4",
        "version": "1.0.0",
        "org_id": "org",
        "type": "memory_save",
        "priority": 2,
        "created_by": {"type": "system", "id": "x"},
        "created_at": "2025-01-01T00:00:00Z",
        "retry_count": 0,
        "max_retries": 2,
    }
    d = decide_retry(msg, RateLimitError("429"))
    assert d.should_retry is True
    assert d.delay_ms == 60000
    assert d.next_priority == 3
    assert d.next_retry_count == 1


