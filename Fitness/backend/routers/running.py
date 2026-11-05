from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.schemas import AthleticSessionIn
from src import garmin_link, running_analytics
from src.database_v2 import add_athletic_session, delete_athletic_session, update_athletic_session

router = APIRouter(prefix="/api/running", tags=["running"])


def _fields(session: AthleticSessionIn) -> dict:
    data = session.model_dump()
    data["session_date"] = session.session_date.isoformat()
    # Pace is always calculated, never typed in.
    data["pace_per_mile"] = running_analytics.pace(session.distance_miles, session.duration_minutes)
    if session.session_type != "running":
        data["run_type"] = None
    if session.session_type != "basketball":
        data["subtype"] = None
    return data


def _check(session: AthleticSessionIn) -> None:
    t = session.session_type
    if t in ("running", "conditioning") and not (session.distance_miles or session.duration_minutes):
        raise HTTPException(status_code=422, detail="Add a distance or a time.")
    if t == "sprint" and not session.sprint_time_seconds:
        raise HTTPException(status_code=422, detail="Add the sprint time.")
    if t == "agility" and not session.sprint_time_seconds:
        raise HTTPException(status_code=422, detail="Add the drill time.")
    if t == "basketball" and not (session.duration_minutes and session.subtype):
        raise HTTPException(status_code=422, detail="Add the kind of session and how many minutes.")
    if t == "plyometric" and not (session.jump_height_inches or session.reps):
        raise HTTPException(status_code=422, detail="Add a jump height or the number of reps.")


@router.get("/sessions")
def list_sessions(limit: int = 100):
    return running_analytics.all_sessions()[:limit]


@router.post("/sessions")
def create_session(session: AthleticSessionIn):
    _check(session)
    data = _fields(session)
    return {"id": add_athletic_session(**data)}


@router.put("/sessions/{session_id}")
def edit_session(session_id: int, session: AthleticSessionIn):
    _check(session)
    if not update_athletic_session(session_id, **_fields(session)):
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"saved": True}


@router.delete("/sessions/{session_id}")
def remove_session(session_id: int):
    if not delete_athletic_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"deleted": True}


@router.get("/summary")
def summary():
    return running_analytics.summary()


# --------------------------------------------------
# Garmin activities -> your log (only when you click Add)
# --------------------------------------------------

class GarminAddIn(BaseModel):
    subtype: Optional[Literal["practice", "game", "skills", "pickup"]] = None
    run_type: Optional[Literal["easy", "recovery", "long", "tempo", "intervals", "race"]] = None
    rpe: Optional[float] = Field(default=None, ge=0, le=10)
    notes: Optional[str] = Field(default=None, max_length=500)


@router.get("/garmin")
def garmin_pending(days: int = 30):
    return garmin_link.pending(days=max(1, min(days, 120)))


@router.post("/garmin/{activity_id}")
def garmin_add(activity_id: int, body: GarminAddIn):
    try:
        return {"id": garmin_link.add_to_log(activity_id, **body.model_dump())}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/garmin/{activity_id}/skip")
def garmin_skip(activity_id: int):
    garmin_link.skip(activity_id)
    return {"skipped": True}
