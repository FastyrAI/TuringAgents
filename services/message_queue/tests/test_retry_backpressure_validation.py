from libs.retry import next_delay_ms
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


