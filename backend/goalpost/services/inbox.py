"""The Proof Inbox: accept, reject and reassign suggestions, attach evidence, unplanned work.

Every function here is an explicit user action. Callers commit.
"""

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from goalpost.errors import Conflict, Invalid, NotFound
from goalpost.models import Event, Evidence, Occurrence, RuleExclusion, Suggestion
from goalpost.models.enums import EvidenceAddedBy, OccurrenceStatus, SuggestionStatus
from goalpost.schemas.inbox import (
    RejectRequest,
    SuggestionRead,
    SuggestionsResponse,
    UnplannedResponse,
)
from goalpost.schemas.planning import OccurrenceRead
from goalpost.sdk.loader import Registry
from goalpost.services.occurrences import mark_done
from goalpost.services.planning import check_monday, get_occurrence, week_end
from goalpost.services.rules import (
    condition_of,
    events_read,
    evidence_window,
    rule_read,
    validate_filter,
)


def get_suggestion(session: Session, suggestion_id: str) -> Suggestion:
    suggestion = session.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise NotFound(f"Suggestion {suggestion_id} not found")
    return suggestion


def suggestion_read(session: Session, registry: Registry, s: Suggestion) -> SuggestionRead:
    return SuggestionRead(
        id=s.id,
        occurrence=OccurrenceRead.model_validate(s.occurrence),
        source=s.source,
        rule=rule_read(session, s.rule) if s.rule else None,
        confidence=s.confidence,
        reason=s.reason,
        status=s.status,
        events=events_read(session, registry, s.events),
        created_at=s.created_at,
        resolved_at=s.resolved_at,
    )


def suggestions_view(
    session: Session, registry: Registry, status: SuggestionStatus | None
) -> SuggestionsResponse:
    query = select(Suggestion).order_by(Suggestion.created_at, Suggestion.id)
    if status is not None:
        query = query.where(Suggestion.status == status)
    return SuggestionsResponse(
        items=[suggestion_read(session, registry, s) for s in session.scalars(query)]
    )


def _require_pending(suggestion: Suggestion) -> None:
    if suggestion.status != SuggestionStatus.PENDING:
        raise Conflict(f"Suggestion is already {suggestion.status.value}", code="already_resolved")


def _complete_with(
    session: Session,
    occurrence: Occurrence,
    events: Sequence[Event],
    added_by: EvidenceAddedBy,
    today: date,
) -> None:
    """Attach events as evidence and mark the occurrence done if it isn't yet.

    It's late only if it was missed and the proof itself came after the evidence window:
    a submission at 11:50 pm that syncs at 3 am still counts as on time.
    """
    if occurrence.status == OccurrenceStatus.SKIPPED:
        raise Conflict("Occurrence was skipped; reopen it first", code="skipped")
    attached = set(
        session.scalars(select(Evidence.event_id).where(Evidence.occurrence_id == occurrence.id))
    )
    for event in events:
        if event.id not in attached:
            session.add(Evidence(occurrence_id=occurrence.id, event_id=event.id, added_by=added_by))
    if occurrence.status != OccurrenceStatus.DONE:
        _, window_end = evidence_window(occurrence)
        late = occurrence.status == OccurrenceStatus.MISSED and any(
            e.local_date > window_end for e in events
        )
        completed_at = max(e.occurred_at for e in events)
        mark_done(session, occurrence, completed_at, late=late, today=today)
    session.flush()
    session.expire(occurrence, ["evidence_events"])


def accept(session: Session, suggestion: Suggestion, now: datetime, today: date) -> Suggestion:
    """Mark the occurrence done and attach the suggestion's events as evidence."""
    _require_pending(suggestion)
    _complete_with(
        session, suggestion.occurrence, suggestion.events, EvidenceAddedBy.SUGGESTION, today
    )
    suggestion.status = SuggestionStatus.ACCEPTED
    suggestion.resolved_at = now
    return suggestion


def reject(
    session: Session, registry: Registry, suggestion: Suggestion, data: RejectRequest, now: datetime
) -> Suggestion:
    """Reject; optionally teach the rule to ignore events like these from now on."""
    _require_pending(suggestion)
    if data.exclusion is not None:
        rule = suggestion.rule
        if rule is None:
            raise Invalid("Only rule suggestions can add an exclusion", field="exclusion")
        condition = condition_of(rule)
        cls = registry.get(rule.connector_type)
        kind = cls.manifest.event_kind(condition.kind) if cls else None
        validate_filter(data.exclusion, kind.rule_fields if kind else [], "exclusion")
        session.add(
            RuleExclusion(
                rule_id=rule.id,
                filter=data.exclusion.model_dump(mode="json"),
                created_from_suggestion_id=suggestion.id,
            )
        )
    suggestion.status = SuggestionStatus.REJECTED
    suggestion.resolved_at = now
    session.flush()
    if suggestion.rule is not None:
        session.expire(suggestion.rule, ["exclusions"])
    return suggestion


def reassign(
    session: Session, suggestion: Suggestion, occurrence_id: str, now: datetime, today: date
) -> Suggestion:
    """Move the evidence to the occurrence it really belongs to, and accept it there."""
    _require_pending(suggestion)
    target = get_occurrence(session, occurrence_id)
    if target.id == suggestion.occurrence_id:
        raise Invalid("That's the occurrence it's already on", field="occurrence_id")
    suggestion.occurrence_id = target.id
    session.flush()
    session.expire(suggestion, ["occurrence"])
    return accept(session, suggestion, now, today)


def attach_evidence(
    session: Session, occurrence: Occurrence, event_ids: Sequence[str], today: date
) -> Occurrence:
    """Attach events by hand. One event may back several occurrences."""
    events = list(session.scalars(select(Event).where(Event.id.in_(list(event_ids)))))
    missing = set(event_ids) - {e.id for e in events}
    if missing:
        raise NotFound(f"Event {sorted(missing)[0]} not found")
    _complete_with(session, occurrence, events, EvidenceAddedBy.MANUAL, today)
    return occurrence


def unplanned_view(session: Session, registry: Registry, monday: date) -> UnplannedResponse:
    """Events in the week that back no occurrence: work you did that wasn't planned."""
    check_monday(monday)
    events = list(
        session.scalars(
            select(Event)
            .where(
                Event.local_date >= monday,
                Event.local_date <= week_end(monday),
                ~exists().where(Evidence.event_id == Event.id),
            )
            .order_by(Event.occurred_at.desc())
        )
    )
    return UnplannedResponse(week_start=monday, items=events_read(session, registry, events))
