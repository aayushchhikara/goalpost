from datetime import date

from fastapi import APIRouter

from goalpost.api.deps import NowDep, RegistryDep, SessionDep, TodayDep
from goalpost.models.enums import SuggestionStatus
from goalpost.schemas.inbox import (
    AttachEvidenceRequest,
    ReassignRequest,
    RejectRequest,
    SuggestionRead,
    SuggestionsResponse,
    UnplannedResponse,
)
from goalpost.schemas.planning import OccurrenceRead
from goalpost.services import inbox
from goalpost.services.dates import week_monday
from goalpost.services.planning import get_occurrence

router = APIRouter(tags=["inbox"])


@router.get("/suggestions", response_model=SuggestionsResponse, operation_id="getSuggestions")
def get_suggestions(
    session: SessionDep, registry: RegistryDep, status: SuggestionStatus | None = None
) -> SuggestionsResponse:
    """The Proof Inbox: suggestions with their occurrence, rule and events. Nothing counts until
    you accept it."""
    return inbox.suggestions_view(session, registry, status)


@router.post(
    "/suggestions/{suggestion_id}/accept",
    response_model=SuggestionRead,
    operation_id="acceptSuggestion",
)
def accept(
    suggestion_id: str, session: SessionDep, registry: RegistryDep, now: NowDep, today: TodayDep
) -> SuggestionRead:
    """Mark the occurrence done and attach the events as evidence."""
    suggestion = inbox.accept(session, inbox.get_suggestion(session, suggestion_id), now, today)
    session.commit()
    return inbox.suggestion_read(session, registry, suggestion)


@router.post(
    "/suggestions/{suggestion_id}/reject",
    response_model=SuggestionRead,
    operation_id="rejectSuggestion",
)
def reject(
    suggestion_id: str,
    body: RejectRequest,
    session: SessionDep,
    registry: RegistryDep,
    now: NowDep,
) -> SuggestionRead:
    """Reject; optionally add an exclusion so the rule ignores events like these."""
    suggestion = inbox.reject(
        session, registry, inbox.get_suggestion(session, suggestion_id), body, now
    )
    session.commit()
    return inbox.suggestion_read(session, registry, suggestion)


@router.post(
    "/suggestions/{suggestion_id}/reassign",
    response_model=SuggestionRead,
    operation_id="reassignSuggestion",
)
def reassign(
    suggestion_id: str,
    body: ReassignRequest,
    session: SessionDep,
    registry: RegistryDep,
    now: NowDep,
    today: TodayDep,
) -> SuggestionRead:
    """Move the evidence to the occurrence you pick, and accept it there."""
    suggestion = inbox.reassign(
        session, inbox.get_suggestion(session, suggestion_id), body.occurrence_id, now, today
    )
    session.commit()
    return inbox.suggestion_read(session, registry, suggestion)


@router.post(
    "/occurrences/{occurrence_id}/evidence",
    response_model=OccurrenceRead,
    operation_id="attachEvidence",
)
def attach_evidence(
    occurrence_id: str, body: AttachEvidenceRequest, session: SessionDep, today: TodayDep
) -> OccurrenceRead:
    """Attach events by hand; marks the occurrence done. One event may back several occurrences."""
    occurrence = inbox.attach_evidence(
        session, get_occurrence(session, occurrence_id), body.event_ids, today
    )
    session.commit()
    return OccurrenceRead.model_validate(occurrence)


@router.get(
    "/events/unplanned", response_model=UnplannedResponse, operation_id="getUnplannedEvents"
)
def get_unplanned(
    session: SessionDep, registry: RegistryDep, today: TodayDep, week: date | None = None
) -> UnplannedResponse:
    """Events in the week (its Monday; default this week) that back no occurrence."""
    return inbox.unplanned_view(session, registry, week or week_monday(today))
