from enum import StrEnum


class WeekStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    CLOSED = "closed"


class TaskKind(StrEnum):
    ONE_OFF = "one_off"
    RECURRING = "recurring"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    DROPPED = "dropped"


class OccurrenceStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    MISSED = "missed"
    SKIPPED = "skipped"


class SyncTrigger(StrEnum):
    STARTUP = "startup"
    SCHEDULE = "schedule"
    MANUAL = "manual"


class SyncStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


class SuggestionSource(StrEnum):
    RULE = "rule"
    AI = "ai"


class SuggestionStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class EvidenceAddedBy(StrEnum):
    SUGGESTION = "suggestion"
    MANUAL = "manual"
