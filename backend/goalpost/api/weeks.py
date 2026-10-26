from datetime import date

from fastapi import APIRouter

from goalpost.api.deps import SessionDep, TodayDep
from goalpost.models.enums import Priority
from goalpost.schemas.planning import BacklogResponse, PlanWeekRequest, TodayResponse, WeekResponse
from goalpost.services.planning import plan_week
from goalpost.services.views import backlog_view, today_view, week_view

router = APIRouter(tags=["weeks"])


@router.get("/weeks/{monday}", response_model=WeekResponse, operation_id="getWeek")
def get_week(monday: date, session: SessionDep, today: TodayDep) -> WeekResponse:
    """Seven days of occurrences, the "any day" tray, adherence and totals."""
    return week_view(session, monday, today)


@router.post("/weeks/{monday}/plan", response_model=WeekResponse, operation_id="planWeek")
def plan(monday: date, body: PlanWeekRequest, session: SessionDep, today: TodayDep) -> WeekResponse:
    """Plan backlog or existing tasks into a week; also adds every open recurring task's days."""
    plan_week(session, monday, [(item.task_id, item.date) for item in body.items], today)
    session.commit()
    return week_view(session, monday, today)


@router.get("/today", response_model=TodayResponse, operation_id="getToday")
def get_today(session: SessionDep, today: TodayDep) -> TodayResponse:
    return today_view(session, today)


@router.get("/backlog", response_model=BacklogResponse, operation_id="getBacklog")
def get_backlog(session: SessionDep, priority: Priority | None = None) -> BacklogResponse:
    """Open one-off tasks not planned into any open week."""
    return backlog_view(session, priority)
