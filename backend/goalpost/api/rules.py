from fastapi import APIRouter, status

from goalpost.api.deps import RegistryDep, SessionDep, TodayDep
from goalpost.schemas.rules import RuleRead, RuleSet
from goalpost.services import rules
from goalpost.services.planning import get_task

router = APIRouter(prefix="/tasks/{task_id}/rule", tags=["rules"])


@router.put("", response_model=RuleRead, operation_id="setRule")
def set_rule(
    task_id: str, body: RuleSet, session: SessionDep, registry: RegistryDep, today: TodayDep
) -> RuleRead:
    """Set or replace the task's rule: connector, event kind, filters and count."""
    task = get_task(session, task_id)
    rule = rules.set_rule(session, registry, task, body)
    rules.evaluate(session, today, [task.id])  # check events already synced
    session.commit()
    return rules.rule_read(session, rule)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, operation_id="deleteRule")
def delete_rule(task_id: str, session: SessionDep) -> None:
    """Remove the rule; the task becomes manual. Pending suggestions from it are dropped."""
    rules.delete_rule(session, get_task(session, task_id))
    session.commit()


@router.delete(
    "/exclusions/{exclusion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteRuleExclusion",
)
def delete_exclusion(task_id: str, exclusion_id: str, session: SessionDep, today: TodayDep) -> None:
    """Remove a learned exclusion, so the rule matches those events again."""
    task = get_task(session, task_id)
    rules.delete_exclusion(session, task, exclusion_id)
    rules.evaluate(session, today, [task.id])
    session.commit()
