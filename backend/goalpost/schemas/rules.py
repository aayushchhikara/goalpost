"""Rules and events: shared by the planning and Proof Inbox schemas."""

import datetime as dt
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# Rules


class FilterOp(StrEnum):
    EQUALS = "equals"  # case-insensitive
    ONE_OF = "one_of"  # value is a list; case-insensitive
    CONTAINS = "contains"  # case-insensitive substring
    MATCHES = "matches"  # glob pattern, e.g. backend/auth/*
    REGEX = "regex"  # e.g. ^chore:
    AT_LEAST = "at_least"  # numeric
    AT_MOST = "at_most"  # numeric


class Filter(BaseModel):
    """A condition on one payload field. A list field, like a commit's paths, matches any item."""

    field: str
    op: FilterOp
    value: str | float | list[str]


class RuleSet(BaseModel):
    """A rule: one connector instance and event kind, filters that must all match, and a count."""

    connector_id: str
    kind: str
    filters: list[Filter] = Field(default_factory=list)
    min_count: int = Field(default=1, ge=1, le=100)


class ExclusionRead(BaseModel):
    id: str
    filter: Filter
    created_from_suggestion_id: str | None
    created_at: dt.datetime


class RuleRead(BaseModel):
    id: str
    task_id: str
    connector_id: str
    connector_type: str
    connector_name: str | None = Field(description="Null if the connector was removed")
    kind: str
    filters: list[Filter]
    min_count: int
    exclusions: list[ExclusionRead] = Field(description="Learned from rejected suggestions")


# Events


class EventRead(BaseModel):
    id: str
    connector_id: str
    connector_name: str
    connector_type: str
    kind: str
    title: str = Field(description="A one-line label, e.g. a commit message or problem name")
    url: str | None
    occurred_at: dt.datetime
    local_date: dt.date
    payload: dict[str, Any]
