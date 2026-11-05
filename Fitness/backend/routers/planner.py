from datetime import date
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src import phase_engine, week_planner
from src.excel_generator import build_weekly_workbook

router = APIRouter(prefix="/api/planner", tags=["planner"])


Status = Literal["open", "busy", "practice", "game"]


class GenerateIn(BaseModel):
    week_start: date
    training_days: Optional[list[int]] = Field(default=None, max_length=7)
    # This week's days (Mon..Sun); omit to use your usual week.
    availability: Optional[list[Status]] = Field(default=None, min_length=7, max_length=7)


class AvailabilityDay(BaseModel):
    weekday: int = Field(ge=0, le=6)
    status: Status
    note: Optional[str] = Field(default=None, max_length=80)


class ItemUpdate(BaseModel):
    item_date: Optional[date] = None
    exercise: Optional[str] = Field(default=None, min_length=1, max_length=80)
    prescribed_weight: Optional[float] = Field(default=None, ge=0, le=2_000)
    sets: Optional[int] = Field(default=None, ge=1, le=30)
    reps: Optional[int] = Field(default=None, ge=1, le=200)
    target_rpe: Optional[float] = Field(default=None, ge=1, le=10)
    planned_work: Optional[str] = Field(default=None, max_length=120)
    target: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=500)
    is_completed: Optional[bool] = None


@router.get("/defaults")
def defaults():
    """Default training days: from the active Goals & Phase plan, else 4 days."""
    plan = phase_engine.get_active_plan()
    statuses = [d["status"] for d in week_planner.get_availability()]
    count = (plan and plan.get("training_days_per_week")) or 4
    return {"training_days": week_planner.pick_lift_days(count, statuses), "availability": statuses}


@router.get("/availability")
def availability():
    return week_planner.get_availability()


@router.put("/availability")
def save_availability(days: list[AvailabilityDay]):
    if sorted(d.weekday for d in days) != list(range(7)):
        raise HTTPException(status_code=422, detail="Send all 7 days, Monday (0) to Sunday (6).")
    return week_planner.save_availability([d.model_dump() for d in days])


@router.get("/week/{week_start}")
def get_week(week_start: date):
    """The saved plan for the week containing `week_start`, or null."""
    return week_planner.get_week(week_start)


@router.post("/generate")
def generate(body: GenerateIn):
    if body.training_days is not None and any(d < 0 or d > 6 for d in body.training_days):
        raise HTTPException(status_code=422, detail="Training days are 0 (Mon) to 6 (Sun).")
    week = week_planner.build_week(body.week_start, body.training_days, availability=body.availability)
    week_planner.save_week(week)
    return week_planner.get_week(body.week_start)


@router.patch("/items/{item_id}")
def update_item(item_id: int, body: ItemUpdate):
    fields = body.model_dump(exclude_unset=True)
    if "item_date" in fields and fields["item_date"] is not None:
        fields["item_date"] = fields["item_date"].isoformat()
    if "is_completed" in fields:
        fields["is_completed"] = 1 if fields["is_completed"] else 0
    if not week_planner.update_item(item_id, fields):
        raise HTTPException(status_code=404, detail="Plan item not found.")
    return {"updated": True}


@router.delete("/items/{item_id}")
def delete_item(item_id: int):
    if not week_planner.delete_item(item_id):
        raise HTTPException(status_code=404, detail="Plan item not found.")
    return {"deleted": True}


@router.get("/week/{week_start}/excel")
def export_excel(week_start: date):
    week = week_planner.get_week(week_start)
    if week is None:
        raise HTTPException(status_code=404, detail="No plan saved for that week.")
    start = date.fromisoformat(week["week_start"])
    path = build_weekly_workbook(
        week_number=start.isocalendar()[1], start_date=start, week_plan=week_planner.to_workbook_plan(week)
    )
    path = Path(path)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )
