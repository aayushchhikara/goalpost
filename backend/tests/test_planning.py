from datetime import UTC, date, datetime, timedelta

import pytest
from goalpost.errors import Conflict, Invalid
from goalpost.models import Occurrence, Task, Week
from goalpost.models.enums import OccurrenceStatus, TaskKind, TaskStatus, WeekStatus
from goalpost.schemas.planning import PlanTarget, TaskCreate, TaskUpdate
from goalpost.services import occurrences, tasks
from goalpost.services.close import close_due
from goalpost.services.planning import find_week, plan_week
from goalpost.services.views import backlog_view, task_detail, week_view
from sqlalchemy import select
from sqlalchemy.orm import Session

MON = date(2026, 10, 26)  # week 44
NEXT_MON = MON + timedelta(days=7)
NOW = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)


def day(n: int) -> date:
    return MON + timedelta(days=n)


def recurring(session: Session, days: list[int], title: str = "LeetCode daily") -> Task:
    data = TaskCreate(title=title, kind=TaskKind.RECURRING, recurrence_days=days)
    return tasks.create_task(session, data, MON)


def one_off(
    session: Session, title: str = "Write CONTRIBUTING", plan: PlanTarget | None = None
) -> Task:
    return tasks.create_task(session, TaskCreate(title=title, plan=plan), MON)


def occurrences_of(
    session: Session, task: Task, monday: date = MON
) -> dict[date | None, Occurrence]:
    week = find_week(session, monday)
    assert week is not None
    rows = session.scalars(
        select(Occurrence).where(Occurrence.task_id == task.id, Occurrence.week_id == week.id)
    )
    return {o.date: o for o in rows}


def dates_of(session: Session, task: Task, monday: date = MON) -> list[date]:
    return sorted(d for d in occurrences_of(session, task, monday) if d is not None)


def statuses(session: Session, task: Task, monday: date = MON) -> dict[date, str]:
    found = occurrences_of(session, task, monday)
    return {d: found[d].status.value for d in dates_of(session, task, monday)}


# Recurring tasks


def test_planning_a_week_generates_one_occurrence_per_recurrence_day(db_session: Session) -> None:
    leetcode = recurring(db_session, [0, 1, 2, 3, 5])  # Mon–Thu + Sat
    plan_week(db_session, MON, [], MON)
    assert dates_of(db_session, leetcode) == [day(0), day(1), day(2), day(3), day(5)]
    assert leetcode.in_backlog is False

    plan_week(db_session, MON, [], MON)  # planning again adds nothing
    assert len(occurrences_of(db_session, leetcode)) == 5


def test_planning_mid_week_only_adds_the_remaining_days(db_session: Session) -> None:
    plan_week(db_session, MON, [], MON)  # the week already exists
    gym = recurring(db_session, [0, 2, 6], title="Gym")
    plan_week(db_session, MON, [(gym.id, None)], today=day(3))  # Thursday
    assert dates_of(db_session, gym) == [day(6)]


def test_recurring_days_never_roll_over(db_session: Session) -> None:
    leetcode = recurring(db_session, [0, 1, 2, 3, 5])
    plan_week(db_session, MON, [], MON)

    close_due(db_session, today=day(2))  # Wednesday morning
    assert statuses(db_session, leetcode) == {
        day(0): "missed",
        day(1): "missed",
        day(2): "pending",
        day(3): "pending",
        day(5): "pending",
    }

    close_due(db_session, today=NEXT_MON)
    assert set(statuses(db_session, leetcode).values()) == {"missed"}
    assert len(occurrences_of(db_session, leetcode)) == 5  # nothing new was created
    assert find_week(db_session, NEXT_MON) is None  # nothing rolled into next week
    assert leetcode.in_backlog is False
    assert backlog_view(db_session).items == []


def test_missed_then_done_is_marked_late(db_session: Session) -> None:
    leetcode = recurring(db_session, [0, 1])
    plan_week(db_session, MON, [], MON)
    close_due(db_session, today=day(1))
    monday = occurrences_of(db_session, leetcode)[day(0)]
    assert monday.status == OccurrenceStatus.MISSED

    occurrences.complete(db_session, monday, NOW, today=day(1))
    assert monday.status == OccurrenceStatus.DONE
    assert monday.late is True
    summary = week_view(db_session, MON, day(1)).adherence[0]
    assert (summary.done, summary.late, summary.planned) == (1, 1, 2)

    occurrences.reopen(db_session, monday, today=day(1))  # undo goes back to missed
    assert (monday.status, monday.late, monday.completed_at) == (
        OccurrenceStatus.MISSED,
        False,
        None,
    )


def test_on_time_completion_is_not_late(db_session: Session) -> None:
    leetcode = recurring(db_session, [0])
    plan_week(db_session, MON, [], MON)
    monday = occurrences_of(db_session, leetcode)[day(0)]
    occurrences.complete(db_session, monday, NOW, today=MON)
    assert monday.late is False
    occurrences.reopen(db_session, monday, today=MON)
    assert monday.status == OccurrenceStatus.PENDING


def test_mid_week_day_change_affects_remaining_days_only(db_session: Session) -> None:
    leetcode = recurring(db_session, [0, 1, 2, 3, 4])  # Mon–Fri
    plan_week(db_session, MON, [], MON)
    plan_week(db_session, NEXT_MON, [], MON)  # next week is already planned too
    occurrences.complete(db_session, occurrences_of(db_session, leetcode)[day(0)], NOW, MON)
    close_due(db_session, today=day(2))  # Tuesday is now missed

    # On Wednesday, switch to Mon, Wed and Sat.
    tasks.update_task(db_session, leetcode, TaskUpdate(recurrence_days=[0, 2, 5]), today=day(2))

    assert statuses(db_session, leetcode) == {
        day(0): "done",  # past days keep their history
        day(1): "missed",
        day(2): "pending",
        day(5): "pending",  # Thu and Fri are gone, Sat is new
    }
    assert dates_of(db_session, leetcode, NEXT_MON) == [
        NEXT_MON,
        NEXT_MON + timedelta(days=2),
        NEXT_MON + timedelta(days=5),
    ]


def test_recurring_days_can_only_change_on_recurring_tasks(db_session: Session) -> None:
    task = one_off(db_session)
    with pytest.raises(Invalid):
        tasks.update_task(db_session, task, TaskUpdate(recurrence_days=[1]), MON)


# One-off tasks and the backlog


def test_new_one_offs_start_in_the_backlog(db_session: Session) -> None:
    task = one_off(db_session)
    assert task.in_backlog is True
    assert [item.task.id for item in backlog_view(db_session).items] == [task.id]


def test_unfinished_one_off_lands_in_the_backlog_when_its_week_closes(db_session: Session) -> None:
    any_day = one_off(db_session, "Auth cleanup", plan=PlanTarget(week_start=MON))
    friday = one_off(db_session, "Out with friends", plan=PlanTarget(week_start=MON, date=day(4)))
    assert not any_day.in_backlog and not friday.in_backlog

    close_due(db_session, today=day(5))  # Saturday: Friday is missed but the week is still open
    assert occurrences_of(db_session, friday)[day(4)].status == OccurrenceStatus.MISSED
    assert occurrences_of(db_session, any_day)[None].status == OccurrenceStatus.PENDING
    assert backlog_view(db_session).items == []

    result = close_due(db_session, today=NEXT_MON)
    assert result.closed_weeks == [MON]
    assert result.returned_to_backlog == 2
    assert occurrences_of(db_session, any_day)[None].status == OccurrenceStatus.MISSED
    backlog = {item.task.id: item for item in backlog_view(db_session).items}
    assert set(backlog) == {any_day.id, friday.id}
    assert backlog[any_day.id].last_planned_week_start == MON
    assert backlog[any_day.id].attempts == 1


def test_done_one_off_stays_out_of_the_backlog(db_session: Session) -> None:
    task = one_off(db_session, plan=PlanTarget(week_start=MON))
    occurrences.complete(db_session, occurrences_of(db_session, task)[None], NOW, MON)
    assert task.status == TaskStatus.DONE
    close_due(db_session, today=NEXT_MON)
    assert task.in_backlog is False


def test_skipped_one_off_also_returns_to_the_backlog(db_session: Session) -> None:
    task = one_off(db_session, plan=PlanTarget(week_start=MON))
    occurrences.skip(occurrences_of(db_session, task)[None])
    close_due(db_session, today=NEXT_MON)
    assert task.in_backlog is True


def test_backlog_task_planned_again_is_carried_over_and_keeps_history(db_session: Session) -> None:
    task = one_off(db_session, plan=PlanTarget(week_start=MON))
    close_due(db_session, today=NEXT_MON)

    plan_week(db_session, NEXT_MON, [(task.id, None)], NEXT_MON)
    assert task.in_backlog is False
    detail = task_detail(db_session, task, NEXT_MON)
    assert [(o.week_start, o.status.value) for o in detail.history] == [
        (NEXT_MON, "pending"),
        (MON, "missed"),
    ]
    assert detail.current_occurrence is not None
    assert detail.current_occurrence.carried_over is True
    assert detail.history[1].carried_over is False


def test_missed_one_off_completed_late_from_the_backlog(db_session: Session) -> None:
    task = one_off(db_session, plan=PlanTarget(week_start=MON))
    close_due(db_session, today=NEXT_MON)
    missed = occurrences_of(db_session, task)[None]
    occurrences.complete(db_session, missed, NOW, NEXT_MON)
    assert missed.late is True
    assert (task.status, task.in_backlog) == (TaskStatus.DONE, False)

    occurrences.reopen(db_session, missed, NEXT_MON)  # back to missed, and back to the backlog
    assert (task.status, task.in_backlog) == (TaskStatus.OPEN, True)


def test_planning_a_one_off_into_another_week_moves_its_pending_occurrence(
    db_session: Session,
) -> None:
    task = one_off(db_session, plan=PlanTarget(week_start=MON))
    plan_week(db_session, NEXT_MON, [(task.id, NEXT_MON)], MON)
    assert occurrences_of(db_session, task) == {}
    assert list(occurrences_of(db_session, task, NEXT_MON)) == [NEXT_MON]


def test_planning_rules(db_session: Session) -> None:
    task = one_off(db_session, plan=PlanTarget(week_start=MON))
    with pytest.raises(Conflict, match="already planned"):
        plan_week(db_session, MON, [(task.id, None)], MON)
    with pytest.raises(Invalid, match="not in the week"):
        one_off(db_session, plan=PlanTarget(week_start=NEXT_MON, date=day(3)))
    with pytest.raises(Invalid, match="not a Monday"):
        plan_week(db_session, day(1), [], MON)
    leetcode = recurring(db_session, [0])
    with pytest.raises(Invalid):
        plan_week(db_session, NEXT_MON, [(leetcode.id, NEXT_MON)], MON)

    close_due(db_session, today=NEXT_MON)
    with pytest.raises(Conflict, match="closed"):
        plan_week(db_session, MON, [], NEXT_MON)
    with pytest.raises(Invalid, match="already passed"):
        plan = PlanTarget(week_start=NEXT_MON, date=NEXT_MON)
        tasks.create_task(
            db_session, TaskCreate(title="Late idea", plan=plan), NEXT_MON + timedelta(1)
        )


# Occurrence actions


def test_skipped_occurrences_do_not_count_against_adherence(db_session: Session) -> None:
    gym = recurring(db_session, [0, 2, 4], title="Gym")
    plan_week(db_session, MON, [], MON)
    days = occurrences_of(db_session, gym)
    occurrences.complete(db_session, days[day(0)], NOW, MON)
    occurrences.skip(days[day(2)])
    adherence = week_view(db_session, MON, MON).adherence[0]
    assert (adherence.done, adherence.planned, adherence.skipped) == (1, 3, 1)
    assert adherence.rate == 0.5  # 1 ÷ (3 − 1)

    with pytest.raises(Conflict):
        occurrences.complete(db_session, days[day(2)], NOW, MON)  # reopen a skip first
    with pytest.raises(Conflict):
        occurrences.skip(days[day(0)])


def test_moving_occurrences(db_session: Session) -> None:
    task = one_off(db_session, plan=PlanTarget(week_start=MON, date=day(1)))
    occurrence = occurrences_of(db_session, task)[day(1)]
    occurrences.move(db_session, occurrence, day(3), MON)
    assert occurrence.date == day(3)
    occurrences.move(db_session, occurrence, None, MON)
    assert occurrence.date is None
    with pytest.raises(Invalid):
        occurrences.move(db_session, occurrence, NEXT_MON, MON)

    leetcode = recurring(db_session, [0, 1])
    plan_week(db_session, MON, [], MON)
    days = occurrences_of(db_session, leetcode)
    with pytest.raises(Invalid):
        occurrences.move(db_session, days[day(1)], None, MON)
    with pytest.raises(Conflict):
        occurrences.move(db_session, days[day(1)], day(0), MON)
    close_due(db_session, today=day(1))
    with pytest.raises(Conflict, match="missed recurring days stay missed"):
        occurrences.move(db_session, days[day(0)], day(2), day(1))


def test_a_missed_one_off_can_move_to_a_later_day_in_its_week(db_session: Session) -> None:
    task = one_off(db_session, plan=PlanTarget(week_start=MON, date=day(0)))
    close_due(db_session, today=day(2))
    occurrence = occurrences_of(db_session, task)[day(0)]
    occurrences.move(db_session, occurrence, day(4), day(2))
    assert (occurrence.date, occurrence.status) == (day(4), OccurrenceStatus.PENDING)


def test_dropping_removes_remaining_days_and_keeps_history(db_session: Session) -> None:
    leetcode = recurring(db_session, [0, 1, 2])
    plan_week(db_session, MON, [], MON)
    occurrences.complete(db_session, occurrences_of(db_session, leetcode)[day(0)], NOW, MON)
    close_due(db_session, today=day(2))  # Tuesday missed

    tasks.drop_task(db_session, leetcode, today=day(2))
    assert leetcode.status == TaskStatus.DROPPED
    assert statuses(db_session, leetcode) == {day(0): "done", day(1): "missed"}
    with pytest.raises(Conflict):
        tasks.drop_task(db_session, leetcode, today=day(2))

    plan_week(db_session, NEXT_MON, [], day(2))  # dropped tasks aren't generated again
    assert occurrences_of(db_session, leetcode, NEXT_MON) == {}


# Close job


def test_close_job_activates_weeks_and_is_idempotent(db_session: Session) -> None:
    plan_week(db_session, NEXT_MON, [], MON)
    week = find_week(db_session, NEXT_MON)
    assert week is not None and week.status == WeekStatus.PLANNING

    result = close_due(db_session, today=NEXT_MON)
    assert result.activated_weeks == [NEXT_MON]
    assert week.status == WeekStatus.ACTIVE

    again = close_due(db_session, today=NEXT_MON)
    assert (again.activated_weeks, again.closed_weeks, again.missed) == ([], [], 0)
    assert db_session.scalars(select(Week)).all() == [week]
