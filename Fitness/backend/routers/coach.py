from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import load_settings
from datetime import date

from src import coach_engine, garmin_store, local_llm, phase_engine

router = APIRouter(prefix="/api/coach", tags=["coach"])


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class AskIn(BaseModel):
    task: Literal["summary", "next_workout", "chat", "phase", "improve"]
    question: Optional[str] = Field(default=None, max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


@router.get("/insights")
def insights():
    """Numbers, flags and the next-workout plan. No LLM involved."""
    return coach_engine.build_insights()


@router.get("/status")
def status():
    model = load_settings()["ollama_model"]
    try:
        models = local_llm.list_local_models()
        ollama_error = None
    except local_llm.LocalLLMError as exc:
        models, ollama_error = [], str(exc)

    return {
        "model": model,
        "model_ready": model in models,
        "local_models": models,
        "ollama_url": local_llm.OLLAMA_URL,
        "ollama_error": ollama_error,
        "garmin": garmin_store.get_last_sync(),
        "garmin_schedule_on": _garmin_schedule_on(),
    }


def _garmin_schedule_on() -> bool:
    """Is the daily 8:00 am sync installed (scripts/garmin_schedule.sh install)?"""
    from pathlib import Path

    return (Path.home() / "Library" / "LaunchAgents" / "com.kaisen.garmin-sync.plist").exists()


@router.post("/ask")
def ask(body: AskIn):
    model = load_settings()["ollama_model"]
    try:
        return coach_engine.ask_coach(
            body.task,
            model,
            question=body.question,
            history=[turn.model_dump() for turn in body.history],
        )
    except local_llm.LocalLLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# --------------------------------------------------
# Profile, phase and plans
# --------------------------------------------------

class ProfileIn(BaseModel):
    sex: Optional[Literal["male", "female"]] = None
    birth_year: Optional[int] = Field(default=None, ge=1920, le=2015)
    height_in: Optional[float] = Field(default=None, ge=48, le=96)
    experience: Optional[Literal["beginner", "intermediate", "advanced"]] = None
    sports: Optional[list[Literal["lifting", "running", "basketball", "other"]]] = Field(default=None, max_length=4)


class PlanIn(BaseModel):
    phase: Literal["cut", "bulk", "maintain", "recomp"]
    weekly_rate_pct: Optional[float] = Field(default=None, ge=-1.5, le=1.0)
    target_weight: Optional[float] = Field(default=None, ge=80, le=600)
    target_date: Optional[date] = None
    training_days_per_week: Optional[int] = Field(default=None, ge=1, le=7)
    priorities: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)
    # Overrides if you want different numbers than the calculation.
    maintenance_kcal: Optional[float] = Field(default=None, ge=1000, le=7000)


class QuickLogIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/log/parse")
def quick_log(body: QuickLogIn):
    """Read a quick 'what I ate / did' message into one day for review. Saves nothing."""
    from src import note_import

    model = load_settings()["ollama_model"]
    try:
        return note_import.parse_quick(body.text, model)
    except local_llm.LocalLLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/profile")
def get_profile():
    return phase_engine.get_profile()


@router.put("/profile")
def put_profile(body: ProfileIn):
    return phase_engine.save_profile(**body.model_dump())


@router.get("/phase")
def phase():
    return phase_engine.phase_overview()


def _computed(body: PlanIn) -> dict:
    balance = phase_engine.energy_balance()
    maintenance = body.maintenance_kcal or balance["maintenance_kcal"]
    weight = balance["latest_weight"]
    if not weight:
        raise HTTPException(status_code=422, detail="Log your body weight first (Body Composition page).")
    if not maintenance:
        raise HTTPException(
            status_code=422,
            detail="Not enough data to estimate maintenance calories yet. Fill in your profile, keep logging, or enter a maintenance number.",
        )
    plan = phase_engine.compute_plan(body.phase, weight, maintenance, body.weekly_rate_pct, body.target_weight)
    return {
        **plan,
        "start_weight": weight,
        "maintenance_kcal": maintenance,
        "target_weight": body.target_weight,
        "target_date": body.target_date.isoformat() if body.target_date else None,
        "training_days_per_week": body.training_days_per_week,
        "priorities": body.priorities,
        "notes": body.notes,
    }


@router.post("/plan/preview")
def preview_plan(body: PlanIn):
    return _computed(body)


@router.post("/plan")
def create_plan(body: PlanIn):
    return phase_engine.save_plan(_computed(body))


@router.delete("/plan")
def end_plan():
    if not phase_engine.end_plan():
        raise HTTPException(status_code=404, detail="No active plan.")
    return {"ended": True}
