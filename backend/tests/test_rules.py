from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from goalpost import sdk
from goalpost.errors import Conflict, Invalid
from goalpost.models import Connector, Event, Evidence, Occurrence, RuleExclusion, Suggestion, Task
from goalpost.models.enums import (
    EvidenceAddedBy,
    OccurrenceStatus,
    SuggestionStatus,
    SyncTrigger,
    TaskKind,
    TaskStatus,
)
from goalpost.schemas.inbox import RejectRequest
from goalpost.schemas.planning import PlanTarget, TaskCreate
from goalpost.schemas.rules import Filter, FilterOp, RuleSet
from goalpost.sdk.loader import Registry
from goalpost.services import inbox, rules, tasks
from goalpost.services.close import close_due
from goalpost.services.dates import local_date, week_monday
from goalpost.services.planning import plan_week
from goalpost.services.settings import ensure_settings
from goalpost.services.sync import sync_connector
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

MON = date(2026, 10, 26)
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=UTC)


def day(n: int) -> date:
    return MON + timedelta(days=n)


class Config(BaseModel):
    username: str = "me"


class Commit(BaseModel):
    repo: str
    message: str
    path: list[str] = []


class FakeGit(sdk.Connector[Config]):
    manifest = sdk.Manifest(
        id="git",
        name="Git",
        version="1",
        sdk_version=sdk.SDK_VERSION,
        config=Config,
        event_kinds=[
            sdk.EventKind(
                name="commit",
                payload=Commit,
                rule_fields=["repo", "message", "path"],
                title_field="message",
            )
        ],
    )
    script: list[sdk.FetchResult] = []

    def test_connection(self, config: Config, secrets: Mapping[str, str]) -> str:
        return "ok"

    def fetch(
        self, config: Config, secrets: Mapping[str, str], cursor: dict[str, Any] | None
    ) -> sdk.FetchResult:
        return FakeGit.script.pop(0)


REGISTRY = Registry(types={"git": FakeGit})


@pytest.fixture
def git(db_session: Session) -> Connector:
    ensure_settings(db_session).timezone = "Asia/Kolkata"
    row = Connector(type="git", name="Personal Git", config={"username": "me"})
    db_session.add(row)
    db_session.commit()
    return row


def commit(
    session: Session, git: Connector, sid: str, on: date, message: str = "feat: x", **extra: Any
) -> Event:
    event = Event(
        connector_id=git.id,
        source_id=sid,
        kind="commit",
        occurred_at=datetime(on.year, on.month, on.day, 12, 0, tzinfo=UTC),
        local_date=on,
        payload={"repo": "goalpost", "message": message, "path": ["backend/x.py"], **extra},
    )
    session.add(event)
    session.flush()
    return event


def one_off(session: Session, plan: PlanTarget, title: str = "Auth cleanup") -> Task:
    return tasks.create_task(session, TaskCreate(title=title, plan=plan), MON)


def recurring(session: Session, days: list[int]) -> Task:
    task = tasks.create_task(
        session, TaskCreate(title="Ship", kind=TaskKind.RECURRING, recurrence_days=days), MON
    )
    plan_week(session, MON, [], MON)
    return task


def rule_on(
    session: Session, git: Connector, task: Task, *filters: Filter, min_count: int = 1
) -> None:
    rules.set_rule(
        session,
        REGISTRY,
        task,
        RuleSet(connector_id=git.id, kind="commit", filters=list(filters), min_count=min_count),
    )


def occ(session: Session, task: Task, on: date | None = None) -> Occurrence:
    rows = session.scalars(select(Occurrence).where(Occurrence.task_id == task.id)).all()
    return next(o for o in rows if o.date == on)


def pending(session: Session) -> list[Suggestion]:
    return list(
        session.scalars(select(Suggestion).where(Suggestion.status == SuggestionStatus.PENDING))
    )


REPO = Filter(field="repo", op=FilterOp.EQUALS, value="goalpost")


# Filters


@pytest.mark.parametrize(
    ("f", "expected"),
    [
        (Filter(field="repo", op=FilterOp.EQUALS, value="GoalPost"), True),
        (Filter(field="repo", op=FilterOp.ONE_OF, value=["dotfiles", "goalpost"]), True),
        (Filter(field="message", op=FilterOp.CONTAINS, value="TOKEN"), True),
        (Filter(field="message", op=FilterOp.REGEX, value="^chore:"), False),
        (Filter(field="path", op=FilterOp.MATCHES, value="backend/auth/*"), True),  # any list item
        (Filter(field="path", op=FilterOp.MATCHES, value="frontend/*"), False),
        (Filter(field="lines", op=FilterOp.AT_LEAST, value=10), True),
        (Filter(field="lines", op=FilterOp.AT_MOST, value=10), False),
        (Filter(field="missing", op=FilterOp.EQUALS, value="x"), False),
    ],
)
def test_filter_matching(f: Filter, expected: bool) -> None:
    payload = {
        "repo": "goalpost",
        "message": "fix token refresh",
        "path": ["README.md", "backend/auth/token.py"],
        "lines": 42,
    }
    assert rules.matches(f, payload) is expected


def test_exclusions_override_filters() -> None:
    chore = Filter(field="message", op=FilterOp.REGEX, value="^chore:")
    assert rules.event_matches([REPO], [chore], {"repo": "goalpost", "message": "feat: x"})
    assert not rules.event_matches([REPO], [chore], {"repo": "goalpost", "message": "chore: bump"})


def test_rules_are_validated(db_session: Session, git: Connector) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON))
    cases = [
        (RuleSet(connector_id="nope", kind="commit"), "not found"),
        (RuleSet(connector_id=git.id, kind="issue"), "no 'issue' events"),
        (
            RuleSet(
                connector_id=git.id,
                kind="commit",
                filters=[Filter(field="author", op=FilterOp.EQUALS, value="x")],
            ),
            "isn't a rule field",
        ),
        (
            RuleSet(
                connector_id=git.id,
                kind="commit",
                filters=[Filter(field="repo", op=FilterOp.ONE_OF, value="x")],
            ),
            "needs a list",
        ),
        (
            RuleSet(
                connector_id=git.id,
                kind="commit",
                filters=[Filter(field="message", op=FilterOp.REGEX, value="(")],
            ),
            "invalid pattern",
        ),
    ]
    for data, message in cases:
        with pytest.raises(Invalid, match=message):
            rules.set_rule(db_session, REGISTRY, task, data)


# The engine


def test_a_dated_occurrence_only_takes_evidence_from_its_day(
    db_session: Session, git: Connector
) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON, date=day(1)))
    rule_on(db_session, git, task, REPO)
    commit(db_session, git, "a", day(0))
    assert rules.evaluate(db_session, MON) == []

    on_day = commit(db_session, git, "b", day(1))
    [suggestion] = rules.evaluate(db_session, MON)
    assert suggestion.occurrence_id == occ(db_session, task, day(1)).id
    assert [e.id for e in suggestion.events] == [on_day.id]
    assert rules.evaluate(db_session, MON) == []  # one pending suggestion at a time


def test_any_day_one_offs_take_evidence_from_their_week(
    db_session: Session, git: Connector
) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON))
    rule_on(db_session, git, task, REPO)
    commit(db_session, git, "before", MON - timedelta(days=1))
    commit(db_session, git, "fri", day(4))
    [suggestion] = rules.evaluate(db_session, MON)
    assert [e.source_id for e in suggestion.events] == ["fri"]


def test_carried_over_tasks_accept_evidence_since_first_planned(
    db_session: Session, git: Connector
) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON))
    close_due(db_session, day(7))  # back to the backlog
    plan_week(db_session, day(7), [(task.id, None)], day(7))
    rule_on(db_session, git, task, REPO)
    commit(db_session, git, "last-week", day(2))
    [suggestion] = rules.evaluate(db_session, day(7))
    assert suggestion.occurrence.week_start == day(7)
    assert [e.source_id for e in suggestion.events] == ["last-week"]


def test_min_count(db_session: Session, git: Connector) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON))
    rule_on(db_session, git, task, REPO, min_count=2)
    commit(db_session, git, "a", day(1))
    assert rules.evaluate(db_session, MON) == []
    commit(db_session, git, "b", day(2))
    [suggestion] = rules.evaluate(db_session, MON)
    assert len(suggestion.events) == 2


def test_recurring_days_each_get_their_own_suggestion(db_session: Session, git: Connector) -> None:
    task = recurring(db_session, [0, 1, 2])
    rule_on(db_session, git, task, REPO)
    commit(db_session, git, "mon", day(0))
    commit(db_session, git, "wed", day(2))
    made = rules.evaluate(db_session, MON)
    assert sorted(s.occurrence.date for s in made) == [day(0), day(2)]  # type: ignore[type-var]


def test_done_skipped_and_dropped_get_nothing(db_session: Session, git: Connector) -> None:
    task = recurring(db_session, [0, 1, 2])
    rule_on(db_session, git, task, REPO)
    occ(db_session, task, day(0)).status = OccurrenceStatus.DONE
    occ(db_session, task, day(1)).status = OccurrenceStatus.SKIPPED
    commit(db_session, git, "mon", day(0))
    commit(db_session, git, "tue", day(1))
    assert rules.evaluate(db_session, MON) == []
    task.status = TaskStatus.DROPPED
    commit(db_session, git, "wed", day(2))
    assert rules.evaluate(db_session, MON) == []


# Proof Inbox actions


def test_accepting_marks_done_with_evidence_and_on_time_after_a_late_sync(
    db_session: Session, git: Connector
) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON, date=day(0)))
    rule_on(db_session, git, task, REPO)
    close_due(db_session, day(1))  # midnight passes before the sync: Monday is missed
    occurrence = occ(db_session, task, day(0))
    assert occurrence.status == OccurrenceStatus.MISSED

    commit(db_session, git, "late-night", day(0))  # 11:50 pm commit, synced at 3 am
    [suggestion] = rules.evaluate(db_session, day(1))
    inbox.accept(db_session, suggestion, NOW, day(1))

    assert (occurrence.status, occurrence.late) == (OccurrenceStatus.DONE, False)
    assert occurrence.completed_at == suggestion.events[0].occurred_at
    assert [e.source_id for e in occurrence.evidence_events] == ["late-night"]
    added_by = db_session.scalars(select(Evidence.added_by)).all()
    assert added_by == [EvidenceAddedBy.SUGGESTION]
    assert (suggestion.status, task.status) == (SuggestionStatus.ACCEPTED, TaskStatus.DONE)
    with pytest.raises(Conflict):
        inbox.accept(db_session, suggestion, NOW, day(1))


def test_rejecting_with_an_exclusion_stops_matching(db_session: Session, git: Connector) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON))
    rule_on(db_session, git, task, REPO)
    commit(db_session, git, "chore", day(1), message="chore: bump deps")
    [suggestion] = rules.evaluate(db_session, MON)

    chore = Filter(field="message", op=FilterOp.REGEX, value="^chore:")
    inbox.reject(db_session, REGISTRY, suggestion, RejectRequest(exclusion=chore), NOW)
    exclusion = db_session.scalars(select(RuleExclusion)).one()
    assert exclusion.created_from_suggestion_id == suggestion.id

    commit(db_session, git, "chore2", day(2), message="chore: lint")
    assert rules.evaluate(db_session, MON) == []  # excluded
    commit(db_session, git, "real", day(3), message="feat: auth")
    [again] = rules.evaluate(db_session, MON)
    assert [e.source_id for e in again.events] == ["real"]


def test_rejected_events_are_not_suggested_again(db_session: Session, git: Connector) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON))
    rule_on(db_session, git, task, REPO)
    commit(db_session, git, "a", day(1))
    [suggestion] = rules.evaluate(db_session, MON)
    inbox.reject(db_session, REGISTRY, suggestion, RejectRequest(), NOW)
    assert rules.evaluate(db_session, MON) == []


def test_reassigning_moves_evidence_and_accepts(db_session: Session, git: Connector) -> None:
    wrong = one_off(db_session, PlanTarget(week_start=MON), title="Wrong")
    right = one_off(db_session, PlanTarget(week_start=MON), title="Right")
    rule_on(db_session, git, wrong, REPO)
    commit(db_session, git, "a", day(1))
    [suggestion] = rules.evaluate(db_session, MON)
    target = occ(db_session, right)
    inbox.reassign(db_session, suggestion, target.id, NOW, MON)
    assert target.status == OccurrenceStatus.DONE
    assert [e.source_id for e in target.evidence_events] == ["a"]
    assert occ(db_session, wrong).status == OccurrenceStatus.PENDING


def test_attaching_evidence_by_hand(db_session: Session, git: Connector) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON, date=day(0)))
    close_due(db_session, day(2))
    occurrence = occ(db_session, task, day(0))
    later = commit(db_session, git, "wed", day(2))
    inbox.attach_evidence(db_session, occurrence, [later.id], day(2))
    # Missed, and the proof came after its day: that one is late.
    assert (occurrence.status, occurrence.late) == (OccurrenceStatus.DONE, True)
    assert db_session.scalars(select(Evidence.added_by)).all() == [EvidenceAddedBy.MANUAL]


def test_unplanned_work(db_session: Session, git: Connector) -> None:
    task = one_off(db_session, PlanTarget(week_start=MON))
    used = commit(db_session, git, "used", day(1))
    commit(db_session, git, "free", day(2), message="dotfiles tweak")
    commit(db_session, git, "next-week", day(8))
    inbox.attach_evidence(db_session, occ(db_session, task), [used.id], MON)
    view = inbox.unplanned_view(db_session, REGISTRY, MON)
    assert [(e.title, e.connector_name) for e in view.items] == [("dotfiles tweak", "Personal Git")]


def test_a_sync_runs_the_rules(db_session: Session, git: Connector) -> None:
    # Syncs evaluate rules against the real clock, so plan into the real current week.
    now = datetime.now(UTC)
    today = local_date(now, "Asia/Kolkata")
    this_monday = week_monday(today)
    task = tasks.create_task(
        db_session, TaskCreate(title="Ship", plan=PlanTarget(week_start=this_monday)), today
    )
    rule_on(db_session, git, task, REPO)
    db_session.commit()
    FakeGit.script = [
        sdk.FetchResult(
            events=[
                sdk.Event(
                    source_id="x",
                    kind="commit",
                    occurred_at=now,
                    payload={"repo": "goalpost", "message": "feat: sync"},
                )
            ],
            cursor=None,
        )
    ]
    sync_connector(db_session, git, SyncTrigger.MANUAL, REGISTRY, env={})
    [suggestion] = pending(db_session)
    assert suggestion.occurrence.task_id == task.id
    assert [e.source_id for e in suggestion.events] == ["x"]
