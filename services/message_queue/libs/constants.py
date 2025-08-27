"""Shared constants for message processing, statuses, and audit event names.

These values centralize naming so producers, workers, and audit pipelines
remain consistent across the codebase and in the database.
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


