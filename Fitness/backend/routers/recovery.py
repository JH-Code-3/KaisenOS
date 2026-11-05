from fastapi import APIRouter, HTTPException

from src.database import add_recovery, add_body_metric
from src.database_v2 import (
    get_recovery_entries,
    delete_recovery_entry,
    get_body_entries,
    delete_body_entry,
    update_recovery_entry,
    update_body_entry,
)
from src.analytics import (
    get_body_weight_trend,
    get_latest_body_weight,
    get_body_weight_summary,
    get_recovery_status,
)

from backend.schemas import RecoveryIn, BodyMetricIn

router = APIRouter(tags=["recovery-and-body"])


def _require_any(values, message):
    if all(value is None for value in values):
        raise HTTPException(status_code=422, detail=message)


@router.get("/api/recovery")
def list_recovery(limit: int = 60):
    return get_recovery_entries(limit=limit)


@router.get("/api/recovery/garmin")
def garmin_recovery(days: int = 30):
    """Garmin nights (read-only, from data/garmin_data.sqlite). Empty if not synced/mapped."""
    from datetime import date, timedelta

    from src import garmin_store

    since = (date.today() - timedelta(days=max(1, min(days, 365)) - 1)).isoformat()
    return {"nights": garmin_store.get_daily_recovery(since), "last_sync": garmin_store.get_last_sync()}


@router.get("/api/recovery/status")
def recovery_status():
    return get_recovery_status()


@router.put("/api/recovery/{entry_id}")
def edit_recovery(entry_id: int, entry: RecoveryIn):
    _require_any(
        (entry.sleep_hours, entry.energy, entry.soreness, entry.pain),
        "At least one recovery measurement is required.",
    )

    if not update_recovery_entry(
        entry_id,
        recovery_date=entry.recovery_date.isoformat(),
        sleep_hours=entry.sleep_hours,
        energy=entry.energy,
        soreness=entry.soreness,
        pain=entry.pain,
        notes=entry.notes,
    ):
        raise HTTPException(status_code=404, detail="Recovery entry not found.")

    return {"saved": True}


@router.delete("/api/recovery/{entry_id}")
def remove_recovery(entry_id: int):
    if not delete_recovery_entry(entry_id):
        raise HTTPException(status_code=404, detail="Recovery entry not found.")

    return {"deleted": True}


@router.post("/api/recovery")
def create_recovery(entry: RecoveryIn):
    has_measurement = any(
        value is not None
        for value in (entry.sleep_hours, entry.energy, entry.soreness, entry.pain)
    )

    if not has_measurement:
        raise HTTPException(
            status_code=422,
            detail="At least one recovery measurement is required.",
        )

    add_recovery(
        recovery_date=entry.recovery_date.isoformat(),
        sleep_hours=entry.sleep_hours,
        energy=entry.energy,
        soreness=entry.soreness,
        pain=entry.pain,
        notes=entry.notes,
    )

    return {"saved": True}


@router.get("/api/body")
def list_body_metrics(limit: int = 120):
    return get_body_entries(limit=limit)


@router.get("/api/body/summary")
def body_summary():
    return get_body_weight_summary()


@router.put("/api/body/{entry_id}")
def edit_body_metric(entry_id: int, entry: BodyMetricIn):
    _require_any(
        (entry.body_weight, entry.body_fat, entry.waist),
        "At least one of body_weight, body_fat, or waist is required.",
    )

    if not update_body_entry(
        entry_id,
        metric_date=entry.metric_date.isoformat(),
        body_weight=entry.body_weight,
        body_fat=entry.body_fat,
        waist=entry.waist,
        notes=entry.notes,
    ):
        raise HTTPException(status_code=404, detail="Body entry not found.")

    return {"saved": True}


@router.delete("/api/body/{entry_id}")
def remove_body_metric(entry_id: int):
    if not delete_body_entry(entry_id):
        raise HTTPException(status_code=404, detail="Body entry not found.")

    return {"deleted": True}


@router.post("/api/body")
def create_body_metric(entry: BodyMetricIn):
    has_metric = any(
        value is not None
        for value in (entry.body_weight, entry.body_fat, entry.waist)
    )

    if not has_metric:
        raise HTTPException(
            status_code=422,
            detail="At least one of body_weight, body_fat, or waist is required.",
        )

    add_body_metric(
        metric_date=entry.metric_date.isoformat(),
        body_weight=entry.body_weight,
        body_fat=entry.body_fat,
        waist=entry.waist,
        notes=entry.notes,
    )

    return {"saved": True}


@router.get("/api/body/weight-trend")
def body_weight_trend():
    return get_body_weight_trend()


@router.get("/api/body/latest-weight")
def latest_weight():
    return get_latest_body_weight()
