from fastapi import APIRouter, status

from goalpost.api.deps import RegistryDep, SessionDep, TodayDep
from goalpost.schemas.planning import TaskCreate, TaskDetailResponse, TaskUpdate
from goalpost.services import tasks
from goalpost.services.planning import get_task
from goalpost.services.rules import evaluate
from goalpost.services.views import task_detail

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post(
    "",
    response_model=TaskDetailResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createTask",
)
def create_task(
    body: TaskCreate, session: SessionDep, registry: RegistryDep, today: TodayDep
) -> TaskDetailResponse:
    """Create a task. Pass `plan` to put it straight into a week or day."""
    task = tasks.create_task(session, body, today)
    evaluate(session, today)
    session.commit()
    return task_detail(session, registry, task, today)


@router.get("/{task_id}", response_model=TaskDetailResponse, operation_id="getTask")
def get_task_detail(
    task_id: str, session: SessionDep, registry: RegistryDep, today: TodayDep
) -> TaskDetailResponse:
    return task_detail(session, registry, get_task(session, task_id), today)


@router.patch("/{task_id}", response_model=TaskDetailResponse, operation_id="updateTask")
def update_task(
    task_id: str, body: TaskUpdate, session: SessionDep, registry: RegistryDep, today: TodayDep
) -> TaskDetailResponse:
    """Edit fields. New recurrence days apply to the remaining days only."""
    task = tasks.update_task(session, get_task(session, task_id), body, today)
    evaluate(session, today, [task.id])
    session.commit()
    return task_detail(session, registry, task, today)


@router.post("/{task_id}/drop", response_model=TaskDetailResponse, operation_id="dropTask")
def drop_task(
    task_id: str, session: SessionDep, registry: RegistryDep, today: TodayDep
) -> TaskDetailResponse:
    """Drop the task. Its remaining pending occurrences go; history is kept."""
    task = tasks.drop_task(session, get_task(session, task_id), today)
    session.commit()
    return task_detail(session, registry, task, today)
