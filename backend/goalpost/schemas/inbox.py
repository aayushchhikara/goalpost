"""The Proof Inbox: suggestions, evidence and unplanned work."""

import datetime as dt

from pydantic import BaseModel, Field

from goalpost.models.enums import SuggestionSource, SuggestionStatus
from goalpost.schemas.planning import OccurrenceRead
from goalpost.schemas.rules import EventRead, Filter, RuleRead


class SuggestionRead(BaseModel):
    id: str
    occurrence: OccurrenceRead
    source: SuggestionSource
    rule: RuleRead | None
    confidence: float | None = Field(description="AI suggestions only")
    reason: str | None
    status: SuggestionStatus
    events: list[EventRead]
    created_at: dt.datetime
    resolved_at: dt.datetime | None


class SuggestionsResponse(BaseModel):
    items: list[SuggestionRead]


class RejectRequest(BaseModel):
    exclusion: Filter | None = Field(
        default=None,
        description="Also stop the rule matching events like these, e.g. message regex ^chore:",
    )


class ReassignRequest(BaseModel):
    occurrence_id: str = Field(description="The occurrence the evidence really belongs to")


class AttachEvidenceRequest(BaseModel):
    event_ids: list[str] = Field(min_length=1)


class UnplannedResponse(BaseModel):
    week_start: dt.date
    items: list[EventRead] = Field(description="Events this week that back no occurrence")
