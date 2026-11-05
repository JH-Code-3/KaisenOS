"""
Pydantic request/response models.

Per README: writes go through schema-validated structured input and
explicit backend functions — never free-form model-generated SQL.
These models are the validation boundary for every write endpoint,
whether the request came from a UI form or the AI Coach's confirmed
write path.
"""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ==================================================
# WORKOUTS (sets)
# ==================================================

class SetIn(BaseModel):
    exercise_name: str = Field(min_length=1)
    set_number: int = Field(ge=1)
    reps: Optional[int] = Field(default=None, ge=0)
    weight: Optional[float] = Field(default=None, ge=0)
    rpe: Optional[float] = Field(default=None, ge=0, le=10)
    rest_seconds: Optional[int] = Field(default=None, ge=0)
    pain: Optional[float] = Field(default=None, ge=0, le=10)
    duration_seconds: Optional[float] = Field(default=None, ge=0)
    is_completed: bool = True
    notes: Optional[str] = None


class WorkoutSessionIn(BaseModel):
    session_date: date
    session_time: Optional[str] = None
    name: Optional[str] = None
    notes: Optional[str] = None
    sets: list[SetIn] = Field(default_factory=list)


# ==================================================
# ATHLETIC / RUNNING SESSIONS
# ==================================================

class AthleticSessionIn(BaseModel):
    session_date: date
    session_type: Literal["running", "sprint", "plyometric", "agility", "conditioning", "basketball"]
    subtype: Optional[Literal["practice", "game", "skills", "pickup"]] = None
    run_type: Optional[Literal["easy", "recovery", "long", "tempo", "intervals", "race"]] = None
    distance_miles: Optional[float] = Field(default=None, gt=0, le=200)
    duration_minutes: Optional[float] = Field(default=None, gt=0, le=1_440)
    sprint_distance_yards: Optional[float] = Field(default=None, gt=0, le=1_000)
    sprint_time_seconds: Optional[float] = Field(default=None, gt=0, le=600)
    jump_height_inches: Optional[float] = Field(default=None, gt=0, le=80)
    reps: Optional[int] = Field(default=None, ge=1, le=500)
    rpe: Optional[float] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = Field(default=None, max_length=1_000)


# ==================================================
# NUTRITION (meals / meal items)
# ==================================================

class MealItemIn(BaseModel):
    food_name: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    serving_unit: Optional[str] = None
    calories: Optional[float] = Field(default=None, ge=0)
    protein_g: Optional[float] = Field(default=None, ge=0)
    carbs_g: Optional[float] = Field(default=None, ge=0)
    fat_g: Optional[float] = Field(default=None, ge=0)
    fiber_g: Optional[float] = Field(default=None, ge=0)
    food_id: Optional[int] = None
    is_estimate: bool = False
    # Remember this food (per-serving values = item values / quantity)
    # so it can be picked from "My foods" next time.
    save_as_food: bool = False


class MealIn(BaseModel):
    meal_date: date
    meal_type: Optional[str] = None
    notes: Optional[str] = None
    items: list[MealItemIn] = Field(default_factory=list, min_length=1)


class NutritionTargetIn(BaseModel):
    effective_date: date
    calories: Optional[float] = Field(default=None, ge=0)
    protein_g: Optional[float] = Field(default=None, ge=0)
    carbs_g: Optional[float] = Field(default=None, ge=0)
    fat_g: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = None



# ==================================================
# RECOVERY / BODY (legacy tables, same shape as coach.py already uses)
# ==================================================

class RecoveryIn(BaseModel):
    recovery_date: date
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    energy: Optional[float] = Field(default=None, ge=0, le=10)
    soreness: Optional[float] = Field(default=None, ge=0, le=10)
    pain: Optional[float] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = None


class BodyMetricIn(BaseModel):
    metric_date: date
    body_weight: Optional[float] = Field(default=None, gt=0)
    body_fat: Optional[float] = Field(default=None, ge=0, le=100)
    waist: Optional[float] = Field(default=None, gt=0)
    notes: Optional[str] = None


# ==================================================
# GOALS
# ==================================================

class GoalIn(BaseModel):
    goal_type: str = Field(min_length=1)
    description: Optional[str] = None
    target_value: Optional[float] = None
    target_date: Optional[date] = None


# ==================================================
# SETTINGS
# ==================================================

class SettingsIn(BaseModel):
    # Name of a locally downloaded Ollama model, e.g. "gpt-oss:20b".
    ollama_model: Optional[str] = Field(default=None, min_length=1, max_length=200)
