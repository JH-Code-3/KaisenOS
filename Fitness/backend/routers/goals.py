from fastapi import APIRouter, HTTPException

from src.database_v2 import add_goal, get_goals, update_goal_status

from backend.schemas import GoalIn

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("")
def list_goals(status: str | None = None):
    return get_goals(status=status)


@router.post("")
def create_goal(goal: GoalIn):
    goal_id = add_goal(
        goal_type=goal.goal_type,
        description=goal.description,
        target_value=goal.target_value,
        target_date=goal.target_date.isoformat() if goal.target_date else None,
    )

    return {"id": goal_id}


@router.patch("/{goal_id}/status")
def set_goal_status(goal_id: int, status: str):
    if status not in {"active", "achieved", "abandoned"}:
        raise HTTPException(status_code=422, detail="Invalid status.")

    updated = update_goal_status(goal_id, status)

    if not updated:
        raise HTTPException(status_code=404, detail="Goal not found.")

    return {"updated": True}
