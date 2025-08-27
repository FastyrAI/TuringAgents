"""Shared constants for message processing, statuses, and audit event names.

These values centralize naming so producers, workers, and audit pipelines
remain consistent across the codebase and in the database.

States (message.status):
- ``QUEUED``: Message created and published to the org queue.
- ``PROCESSING``: Worker dequeued and started handling the message.
- ``COMPLETED``: Business logic finished successfully; final response emitted.
- ``FAILED``: Handler raised an exception for this attempt.
- ``RETRYING``: A retry has been scheduled (in a delay queue) after a failure.
- ``DEAD_LETTERED``: Terminal failure; message shipped to DLQ.
- ``DUPLICATE``: Idempotency detected a duplicate message; processing skipped.
- ``QUARANTINED``: Detected as poison (too many failures); withheld from processing.

Audit events (message_events.event_type):
- ``created``: Producer constructed a message (before or at enqueue time).
- ``enqueued``: Message published to the org requests exchange/queue.
- ``promoted``: Priority promotion (e.g., P3→P2) occurred.
- ``dequeued``: Worker dequeued the message from the org request queue.
- ``processing``: Worker started processing the message.
- ``completed``: Handler completed successfully.
- ``failed``: Handler failed for this attempt.
- ``retry_scheduled``: Retry scheduled with delay and incremented retry count.
- ``dead_letter``: Message sent to DLQ after exhausting retries or fatal error.
- ``duplicate_skipped``: Duplicate detected; processing intentionally skipped.
- ``poison_quarantined``: Poison detection threshold reached; quarantined.
- ``conflict_detected``: Detected potential concurrency/ownership conflict.
- ``conflict_resolved``: Conflict auto-resolved.
- ``conflict_resolution_failed``: Conflict could not be resolved; human action needed.
"""
# Constants for message processing and audit semantics

DEFAULT_RETRY_DELAYS_MS = [1000, 2000, 4000, 8000]

# Message statuses
STATUS_QUEUED = "QUEUED"
STATUS_PROCESSING = "PROCESSING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_RETRYING = "RETRYING"
STATUS_DEAD_LETTERED = "DEAD_LETTERED"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_QUARANTINED = "QUARANTINED"

# Event types
EVENT_CREATED = "created"
EVENT_ENQUEUED = "enqueued"
EVENT_PROMOTED = "promoted"
EVENT_DEQUEUED = "dequeued"
EVENT_PROCESSING = "processing"
EVENT_COMPLETED = "completed"
EVENT_FAILED = "failed"
EVENT_RETRY_SCHEDULED = "retry_scheduled"
EVENT_DEAD_LETTER = "dead_letter"
EVENT_DUPLICATE_SKIPPED = "duplicate_skipped"
EVENT_POISON_QUARANTINED = "poison_quarantined"

# Conflict detection events
EVENT_CONFLICT_DETECTED = "conflict_detected"
EVENT_CONFLICT_RESOLVED = "conflict_resolved"
EVENT_CONFLICT_RESOLUTION_FAILED = "conflict_resolution_failed"


