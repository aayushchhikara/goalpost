"""Rules and the rule engine. The engine only ever creates suggestions; nothing becomes done here.

A rule reads one connector instance and event kind. An event matches when every filter matches
and no exclusion does. Matching events inside the occurrence's evidence window, at least
`min_count` of them, become one pending suggestion. Callers commit.
"""

import fnmatch
import re
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from goalpost.errors import Invalid, NotFound
from goalpost.models import (
    Connector,
    Event,
    Occurrence,
    Rule,
    RuleExclusion,
    Suggestion,
    SuggestionEvent,
    Task,
)
from goalpost.models.enums import (
    OccurrenceStatus,
    SuggestionSource,
    SuggestionStatus,
    TaskKind,
    TaskStatus,
)
from goalpost.schemas.rules import EventRead, ExclusionRead, Filter, FilterOp, RuleRead, RuleSet
from goalpost.sdk.loader import Registry
from goalpost.services.planning import week_end

# Occurrences whose evidence window ended longer ago than this aren't re-checked. A week covers
# late syncs (a Sunday 11:50 pm submission synced on Monday) without rescanning all history.
LOOKBACK_DAYS = 7

# Filter matching


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _test(op: FilterOp, actual: Any, expected: Any) -> bool:
    text = str(actual)
    match op:
        case FilterOp.EQUALS:
            return text.casefold() == str(expected).casefold()
        case FilterOp.ONE_OF:
            return text.casefold() in {str(v).casefold() for v in _as_list(expected)}
        case FilterOp.CONTAINS:
            return str(expected).casefold() in text.casefold()
        case FilterOp.MATCHES:
            return fnmatch.fnmatchcase(text, str(expected))
        case FilterOp.REGEX:
            return re.search(str(expected), text) is not None
        case FilterOp.AT_LEAST | FilterOp.AT_MOST:
            try:
                number, bound = float(actual), float(expected)
            except (TypeError, ValueError):
                return False
            return number >= bound if op == FilterOp.AT_LEAST else number <= bound


def matches(f: Filter, payload: dict[str, Any]) -> bool:
    """True if the payload field satisfies the filter. A list field matches if any item does."""
    return any(_test(f.op, item, f.value) for item in _as_list(payload.get(f.field)))


def event_matches(
    filters: Sequence[Filter], exclusions: Sequence[Filter], payload: dict[str, Any]
) -> bool:
    return all(matches(f, payload) for f in filters) and not any(
        matches(x, payload) for x in exclusions
    )


# Rules


def condition_of(rule: Rule) -> RuleSet:
    return RuleSet.model_validate(rule.condition)


def validate_filter(f: Filter, rule_fields: Iterable[str], label: str) -> None:
    fields = list(rule_fields)
    if f.field not in fields:
        raise Invalid(f"{label}: {f.field!r} isn't a rule field; use one of {fields}", field=label)
    if f.op == FilterOp.ONE_OF and not isinstance(f.value, list):
        raise Invalid(f"{label}: one_of needs a list of values", field=label)
    if f.op != FilterOp.ONE_OF and isinstance(f.value, list):
        raise Invalid(f"{label}: {f.op.value} needs a single value", field=label)
    if f.op in (FilterOp.AT_LEAST, FilterOp.AT_MOST):
        try:
            float(f.value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise Invalid(f"{label}: {f.op.value} needs a number", field=label) from None
    if f.op == FilterOp.REGEX:
        try:
            re.compile(str(f.value))
        except re.error as exc:
            raise Invalid(f"{label}: invalid pattern: {exc}", field=label) from exc


def _rule_fields(
    session: Session, registry: Registry, connector_id: str, kind: str
) -> tuple[Connector, list[str]]:
    connector = session.get(Connector, connector_id)
    if connector is None:
        raise Invalid(f"Connector {connector_id} not found", field="connector_id")
    cls = registry.get(connector.type)
    if cls is None:
        raise Invalid(f"Connector type {connector.type!r} isn't installed", field="connector_id")
    event_kind = cls.manifest.event_kind(kind)
    if event_kind is None:
        kinds = [k.name for k in cls.manifest.event_kinds]
        raise Invalid(
            f"{cls.manifest.name} has no {kind!r} events; use one of {kinds}", field="kind"
        )
    return connector, event_kind.rule_fields


def set_rule(session: Session, registry: Registry, task: Task, data: RuleSet) -> Rule:
    """Create or replace the task's rule. Learned exclusions stay if the source is unchanged."""
    connector, fields = _rule_fields(session, registry, data.connector_id, data.kind)
    for i, f in enumerate(data.filters):
        validate_filter(f, fields, f"filters.{i}")

    rule = session.scalar(select(Rule).where(Rule.task_id == task.id))
    if rule is None:
        rule = Rule(task_id=task.id, connector_type=connector.type)
        session.add(rule)
    else:
        old = condition_of(rule)
        if (old.connector_id, old.kind) != (data.connector_id, data.kind):
            # Exclusions name fields of the old source, so they don't carry over.
            session.execute(delete(RuleExclusion).where(RuleExclusion.rule_id == rule.id))
    rule.connector_type = connector.type
    rule.condition = data.model_dump(mode="json")
    # Pending suggestions were made under the old rule; let the engine re-suggest under the new one.
    _drop_pending_suggestions(session, task)
    session.flush()
    session.expire(task, ["rule"])
    return rule


def delete_rule(session: Session, task: Task) -> None:
    rule = session.scalar(select(Rule).where(Rule.task_id == task.id))
    if rule is None:
        raise NotFound("This task has no rule")
    _drop_pending_suggestions(session, task)
    session.delete(rule)
    session.flush()
    session.expire(task, ["rule"])


def delete_exclusion(session: Session, task: Task, exclusion_id: str) -> None:
    exclusion = session.get(RuleExclusion, exclusion_id)
    if exclusion is None or task.rule is None or exclusion.rule_id != task.rule.id:
        raise NotFound(f"Exclusion {exclusion_id} not found on this task's rule")
    session.delete(exclusion)
    session.flush()
    session.expire(task.rule, ["exclusions"])


def _drop_pending_suggestions(session: Session, task: Task) -> None:
    pending = (
        select(Suggestion.id)
        .join(Occurrence)
        .where(Occurrence.task_id == task.id, Suggestion.status == SuggestionStatus.PENDING)
    )
    session.execute(delete(Suggestion).where(Suggestion.id.in_(pending)))


def rule_read(session: Session, rule: Rule) -> RuleRead:
    condition = condition_of(rule)
    connector = session.get(Connector, condition.connector_id)
    return RuleRead(
        id=rule.id,
        task_id=rule.task_id,
        connector_id=condition.connector_id,
        connector_type=rule.connector_type,
        connector_name=connector.name if connector else None,
        kind=condition.kind,
        filters=condition.filters,
        min_count=condition.min_count,
        exclusions=[
            ExclusionRead(
                id=x.id,
                filter=Filter.model_validate(x.filter),
                created_from_suggestion_id=x.created_from_suggestion_id,
                created_at=x.created_at,
            )
            for x in rule.exclusions
        ],
    )


# Events


def events_read(session: Session, registry: Registry, events: Sequence[Event]) -> list[EventRead]:
    connectors = {
        c.id: c
        for c in session.scalars(
            select(Connector).where(Connector.id.in_({e.connector_id for e in events}))
        )
    }
    out = []
    for event in events:
        connector = connectors.get(event.connector_id)
        cls = registry.get(connector.type) if connector else None
        kind = cls.manifest.event_kind(event.kind) if cls else None
        title_field = kind.title_field if kind else None
        title = event.payload.get(title_field) if title_field else None
        out.append(
            EventRead(
                id=event.id,
                connector_id=event.connector_id,
                connector_name=connector.name if connector else "Removed connector",
                connector_type=connector.type if connector else "",
                kind=event.kind,
                title=str(title or event.payload.get("title") or event.kind),
                url=event.payload.get("url"),
                occurred_at=event.occurred_at,
                local_date=event.local_date,
                payload=event.payload,
            )
        )
    return out


# The engine


def evidence_window(occurrence: Occurrence) -> tuple[date, date]:
    """A dated occurrence: its day. "Any day": its week, or since the week it was first planned."""
    if occurrence.date is not None:
        return occurrence.date, occurrence.date
    start = occurrence.week_start
    first = occurrence.task.first_planned_week_start
    if occurrence.carried_over and first is not None:
        start = first
    return start, week_end(occurrence.week_start)


def _candidates(session: Session, today: date, task_ids: Iterable[str] | None) -> list[Occurrence]:
    query = (
        select(Occurrence)
        .join(Task, Occurrence.task_id == Task.id)
        .join(Rule, Rule.task_id == Task.id)
        .where(
            Occurrence.status.in_([OccurrenceStatus.PENDING, OccurrenceStatus.MISSED]),
            Task.status == TaskStatus.OPEN,
        )
    )
    if task_ids is not None:
        query = query.where(Task.id.in_(list(task_ids)))
    cutoff = today - timedelta(days=LOOKBACK_DAYS)
    candidates = [o for o in session.scalars(query) if evidence_window(o)[1] >= cutoff]
    # A carried-over one-off collects evidence only on its latest occurrence, whose window
    # already reaches back to when it was first planned. Otherwise the same commit would be
    # suggested for last week's missed slot too.
    latest: dict[str, Occurrence] = {}
    for o in candidates:
        if o.task.kind == TaskKind.ONE_OFF:
            current = latest.get(o.task_id)
            if current is None or o.week_start > current.week_start:
                latest[o.task_id] = o
    return [o for o in candidates if o.task.kind != TaskKind.ONE_OFF or latest[o.task_id] is o]


def evaluate(
    session: Session, today: date, task_ids: Iterable[str] | None = None
) -> list[Suggestion]:
    """Create suggestions for open occurrences whose rule is now satisfied. Safe to rerun."""
    created: list[Suggestion] = []
    for occurrence in _candidates(session, today, task_ids):
        rule = occurrence.task.rule
        if rule is None or occurrence.pending_suggestion is not None:
            continue
        condition = condition_of(rule)
        exclusions = [Filter.model_validate(x.filter) for x in rule.exclusions]
        start, end = evidence_window(occurrence)
        rejected = set(
            session.scalars(
                select(SuggestionEvent.event_id)
                .join(Suggestion, Suggestion.id == SuggestionEvent.suggestion_id)
                .where(
                    Suggestion.occurrence_id == occurrence.id,
                    Suggestion.status == SuggestionStatus.REJECTED,
                )
            )
        )
        events = session.scalars(
            select(Event)
            .where(
                Event.connector_id == condition.connector_id,
                Event.kind == condition.kind,
                Event.local_date >= start,
                Event.local_date <= end,
            )
            .order_by(Event.occurred_at)
        )
        matched = [
            e
            for e in events
            if e.id not in rejected and event_matches(condition.filters, exclusions, e.payload)
        ]
        if len(matched) < condition.min_count:
            continue
        suggestion = Suggestion(
            occurrence_id=occurrence.id, source=SuggestionSource.RULE, rule_id=rule.id
        )
        session.add(suggestion)
        session.flush()
        session.add_all(
            SuggestionEvent(suggestion_id=suggestion.id, event_id=e.id) for e in matched
        )
        session.flush()
        session.expire(occurrence, ["suggestions"])
        created.append(suggestion)
    return created
