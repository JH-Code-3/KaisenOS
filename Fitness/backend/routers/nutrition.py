from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from src.database_v2 import (
    add_meal,
    add_meal_item,
    get_meals,
    get_daily_nutrition_totals,
    add_nutrition_target,
    get_latest_nutrition_target,
    search_foods,
    add_food,
    find_food_by_name,
    delete_meal,
    get_nutrition_target_for,
    get_legacy_nutrition_for_date,
)
from src.database import get_nutrition

from backend.schemas import MealIn, NutritionTargetIn

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])


@router.get("/meals")
def list_meals(meal_date: str | None = None, limit: int = 20):
    return get_meals(meal_date=meal_date, limit=limit)


@router.post("/meals")
def create_meal(meal: MealIn):
    """
    Save a confirmed meal plus its individual food items. The frontend
    (manual form or AI-coach structured preview) is responsible for
    showing this exact payload to the athlete before calling this
    endpoint — the backend never writes an unconfirmed guess.
    """

    meal_id = add_meal(
        meal_date=meal.meal_date.isoformat(),
        meal_type=meal.meal_type,
        notes=meal.notes,
    )

    for item in meal.items:
        food_id = item.food_id

        if item.save_as_food and food_id is None:
            food_id = _remember_food(item)

        add_meal_item(
            meal_id=meal_id,
            food_name=item.food_name,
            quantity=item.quantity,
            serving_unit=item.serving_unit,
            calories=item.calories,
            protein_g=item.protein_g,
            carbs_g=item.carbs_g,
            fat_g=item.fat_g,
            fiber_g=item.fiber_g,
            food_id=food_id,
            is_estimate=item.is_estimate,
        )

    meals = get_meals(meal_date=meal.meal_date.isoformat(), limit=50)
    saved = next((m for m in meals if m["id"] == meal_id), None)

    if saved is None:
        raise HTTPException(status_code=500, detail="Meal save could not be verified.")

    return saved


def _remember_food(item):
    """Return the id of a saved food matching this item, creating it if new."""

    existing = find_food_by_name(item.food_name)

    if existing:
        return existing["id"]

    def per_serving(value):
        return None if value is None else round(value / item.quantity, 2)

    return add_food(
        name=item.food_name.strip(),
        serving_size=1,
        serving_unit=item.serving_unit or "serving",
        calories=per_serving(item.calories),
        protein_g=per_serving(item.protein_g),
        carbs_g=per_serving(item.carbs_g),
        fat_g=per_serving(item.fat_g),
        fiber_g=per_serving(item.fiber_g),
        source="manual",
        is_estimate=item.is_estimate,
    )


@router.delete("/meals/{meal_id}")
def remove_meal(meal_id: int):
    if not delete_meal(meal_id):
        raise HTTPException(status_code=404, detail="Meal not found.")

    return {"deleted": True}


@router.get("/day/{day}")
def day_view(day: date):
    """Everything the Nutrition page needs for one day in one call."""

    day_str = day.isoformat()

    return {
        "date": day_str,
        "meals": list(reversed(get_meals(meal_date=day_str))),
        "legacy_entries": get_legacy_nutrition_for_date(day_str),
        "totals": get_daily_nutrition_totals(day_str),
        "target": get_nutrition_target_for(day_str),
    }


@router.get("/foods")
def list_foods(limit: int = 500):
    return search_foods("", limit=limit)


@router.get("/foods/search")
def search_food_catalog(q: str, limit: int = 20):
    return search_foods(q, limit=limit)


@router.get("/daily/{nutrition_date}")
def daily_totals(nutrition_date: str):
    return get_daily_nutrition_totals(nutrition_date)


@router.get("/weekly-average")
def weekly_average(end_date: str | None = None):
    end = date.fromisoformat(end_date) if end_date else date.today()
    start = end - timedelta(days=6)

    days = []
    day = start

    while day <= end:
        days.append(get_daily_nutrition_totals(day.isoformat()))
        day += timedelta(days=1)

    logged_days = [d for d in days if d["calories"] > 0]
    count = len(logged_days) or 1

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days_logged": len(logged_days),
        "avg_calories": round(sum(d["calories"] for d in logged_days) / count, 1),
        "avg_protein_g": round(sum(d["protein_g"] for d in logged_days) / count, 1),
        "avg_carbs_g": round(sum(d["carbs_g"] for d in logged_days) / count, 1),
        "avg_fat_g": round(sum(d["fat_g"] for d in logged_days) / count, 1),
        "days": days,
    }


@router.get("/targets/latest")
def latest_target():
    target = get_latest_nutrition_target()

    if target is None:
        return None

    return target


@router.post("/targets")
def create_target(target: NutritionTargetIn):
    target_id = add_nutrition_target(
        effective_date=target.effective_date.isoformat(),
        calories=target.calories,
        protein_g=target.protein_g,
        carbs_g=target.carbs_g,
        fat_g=target.fat_g,
        notes=target.notes,
    )

    return {"id": target_id}


@router.get("/legacy")
def legacy_nutrition_rows(limit: int = 20):
    """Read-only access to rows coach.py wrote to the original flat table."""
    return get_nutrition()[:limit]
