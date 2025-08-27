import os

from libs.config import Settings


def test_settings_dlq_retention_default():
    # Default should be 90 when env not set
    os.environ.pop("DLQ_RETENTION_DAYS", None)
    s = Settings()
    assert s.dlq_retention_days == 90


def test_settings_dlq_retention_env_override(monkeypatch):
    monkeypatch.setenv("DLQ_RETENTION_DAYS", "7")
    s = Settings()
    assert s.dlq_retention_days == 7

