"""Database tables. Importing this package registers every model on Base.metadata."""

from goalpost.models.evidence import (
    Connector,
    Event,
    Evidence,
    Rule,
    RuleExclusion,
    Suggestion,
    SuggestionEvent,
    SyncRun,
)
from goalpost.models.planning import Occurrence, Task, UserSettings, Week

__all__ = [
    "Connector",
    "Event",
    "Evidence",
    "Occurrence",
    "Rule",
    "RuleExclusion",
    "Suggestion",
    "SuggestionEvent",
    "SyncRun",
    "Task",
    "UserSettings",
    "Week",
]
