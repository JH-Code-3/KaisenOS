from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import load_settings
from src import local_llm, note_import

router = APIRouter(prefix="/api/import", tags=["import"])

MealType = Optional[Literal["breakfast", "lunch", "dinner", "snack", "pre-workout", "post-workout"]]


class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=note_import.MAX_TEXT_CHARS)


class ItemIn(BaseModel):
    food_name: str = Field(min_length=1, max_length=120)
    quantity: Optional[float] = Field(default=None, gt=0, le=10_000)
    serving_unit: Optional[str] = Field(default=None, max_length=40)
    calories: Optional[float] = Field(default=None, ge=0, le=10_000)
    protein_g: Optional[float] = Field(default=None, ge=0, le=1_000)
    carbs_g: Optional[float] = Field(default=None, ge=0, le=2_000)
    fat_g: Optional[float] = Field(default=None, ge=0, le=1_000)
    is_estimate: bool = False


class MealIn(BaseModel):
    meal_type: MealType = None
    items: list[ItemIn] = Field(min_length=1)


class ExerciseIn(BaseModel):
    exercise: str = Field(min_length=1, max_length=80)
    weight: Optional[float] = Field(default=None, ge=0, le=2_000)
    reps: int = Field(ge=1, le=200)
    sets: int = Field(ge=1, le=30)
    rpe: Optional[float] = Field(default=None, ge=1, le=10)


class WorkoutIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    exercises: list[ExerciseIn] = Field(min_length=1)


class ActivityIn(BaseModel):
    session_type: Literal["running", "basketball", "conditioning", "sprint", "plyometric", "agility"]
    subtype: Optional[Literal["practice", "game", "skills", "pickup"]] = None
    run_type: Optional[Literal["easy", "recovery", "long", "tempo", "intervals", "race"]] = None
    distance_miles: Optional[float] = Field(default=None, gt=0, le=200)
    duration_minutes: Optional[float] = Field(default=None, gt=0, le=1_440)
    rpe: Optional[float] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = Field(default=None, max_length=500)


class RecoveryIn(BaseModel):
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    energy: Optional[float] = Field(default=None, ge=0, le=10)
    soreness: Optional[float] = Field(default=None, ge=0, le=10)
    pain: Optional[float] = Field(default=None, ge=0, le=10)


class DayIn(BaseModel):
    date: date
    meals: list[MealIn] = Field(default_factory=list)
    workouts: list[WorkoutIn] = Field(default_factory=list)
    activities: list[ActivityIn] = Field(default_factory=list)
    body_weight: Optional[float] = Field(default=None, ge=50, le=1_000)
    recovery: Optional[RecoveryIn] = None
    notes: Optional[str] = Field(default=None, max_length=2_000)


class CommitIn(BaseModel):
    days: list[DayIn] = Field(min_length=1, max_length=400)
    source: Literal["notes", "coach"] = "notes"


@router.post("/parse")
def start_parse(body: ParseIn):
    model = load_settings()["ollama_model"]
    try:
        job_id = note_import.start_parse_job(body.text, model)
    except local_llm.LocalLLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = note_import.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Import job not found (the server may have restarted).")
    return job


@router.post("/commit")
def commit(body: CommitIn):
    if any(d.date > date.today() for d in body.days):
        raise HTTPException(status_code=422, detail="Dates can't be in the future.")
    days = [d.model_dump(mode="json") for d in body.days]
    for d in days:
        if d["recovery"] and all(v is None for v in d["recovery"].values()):
            d["recovery"] = None
    return note_import.commit_days(days, source=body.source)


@router.get("/batches")
def batches():
    return note_import.list_batches()


@router.post("/batches/{batch_id}/undo")
def undo(batch_id: int):
    if not note_import.undo_batch(batch_id):
        raise HTTPException(status_code=404, detail="Import not found or already undone.")
    return {"undone": True}
