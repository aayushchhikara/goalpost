from fastapi import APIRouter

from goalpost.api.deps import NowDep, SessionDep, TodayDep
from goalpost.schemas.planning import OccurrenceRead, OccurrenceUpdate
from goalpost.services import occurrences
from goalpost.services.planning import get_occurrence

router = APIRouter(prefix="/occurrences", tags=["occurrences"])


@router.post(
    "/{occurrence_id}/complete", response_model=OccurrenceRead, operation_id="completeOccurrence"
)
def complete(
    occurrence_id: str, session: SessionDep, now: NowDep, today: TodayDep
) -> OccurrenceRead:
    """Mark done by hand. A missed occurrence is marked late."""
    occurrence = occurrences.complete(session, get_occurrence(session, occurrence_id), now, today)
    session.commit()
    return OccurrenceRead.model_validate(occurrence)


@router.post("/{occurrence_id}/skip", response_model=OccurrenceRead, operation_id="skipOccurrence")
def skip(occurrence_id: str, session: SessionDep) -> OccurrenceRead:
    """Skip deliberately; skipped occurrences don't count against adherence."""
    occurrence = occurrences.skip(get_occurrence(session, occurrence_id))
    session.commit()
    return OccurrenceRead.model_validate(occurrence)


@router.post(
    "/{occurrence_id}/reopen", response_model=OccurrenceRead, operation_id="reopenOccurrence"
)
def reopen(occurrence_id: str, session: SessionDep, today: TodayDep) -> OccurrenceRead:
    """Undo a complete or skip."""
    occurrence = occurrences.reopen(session, get_occurrence(session, occurrence_id), today)
    session.commit()
    return OccurrenceRead.model_validate(occurrence)


@router.patch("/{occurrence_id}", response_model=OccurrenceRead, operation_id="moveOccurrence")
def move(
    occurrence_id: str, body: OccurrenceUpdate, session: SessionDep, today: TodayDep
) -> OccurrenceRead:
    """Move to another remaining day of the same week, or to "any day"."""
    occurrence = occurrences.move(session, get_occurrence(session, occurrence_id), body.date, today)
    session.commit()
    return OccurrenceRead.model_validate(occurrence)
