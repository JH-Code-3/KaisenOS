from fastapi import APIRouter, HTTPException

from src.database_v2 import (
    add_workout_session,
    add_workout_set,
    get_workout_sessions,
    get_workout_session,
    delete_workout_set,
    delete_workout_session,
    get_exercise_names,
)
from src.analytics import (
    get_exercise_analysis,
    get_exercise_trend,
    get_progression_recommendation,
    analyze_session_sets,
    get_weekly_training_volume,
)

from backend.schemas import WorkoutSessionIn

router = APIRouter(prefix="/api/workouts", tags=["workouts"])


@router.get("/sessions")
def list_sessions(limit: int = 20):
    sessions = get_workout_sessions(limit=limit)

    for session in sessions:
        session["analysis"] = analyze_session_sets(session)

    return sessions


@router.get("/sessions/{session_id}")
def get_session(session_id: int):
    session = get_workout_session(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    session["analysis"] = analyze_session_sets(session)
    return session


@router.post("/sessions")
def create_session(session: WorkoutSessionIn):
    """
    Create a workout session with its sets in one request. Mirrors the
    AI Coach's confirm-before-write rule: the frontend is expected to
    show the parsed/entered sets for confirmation before calling this.
    """

    session_id = add_workout_session(
        session_date=session.session_date.isoformat(),
        session_time=session.session_time,
        name=session.name,
        notes=session.notes,
    )

    for set_in in session.sets:
        add_workout_set(
            session_id=session_id,
            exercise_name=set_in.exercise_name,
            set_number=set_in.set_number,
            reps=set_in.reps,
            weight=set_in.weight,
            rpe=set_in.rpe,
            rest_seconds=set_in.rest_seconds,
            pain=set_in.pain,
            duration_seconds=set_in.duration_seconds,
            is_completed=set_in.is_completed,
            notes=set_in.notes,
        )

    return get_workout_session(session_id)


@router.delete("/sessions/{session_id}")
def remove_session(session_id: int):
    if not delete_workout_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    return {"deleted": True}


@router.get("/exercises")
def list_exercise_names():
    return get_exercise_names()


@router.delete("/sets/{set_id}")
def remove_set(set_id: int):
    deleted = delete_workout_set(set_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Set not found.")

    return {"deleted": True}


@router.get("/exercises/{exercise_name}/analysis")
def exercise_analysis(exercise_name: str):
    analysis = get_exercise_analysis(exercise_name)

    if analysis is None:
        raise HTTPException(status_code=404, detail="No workout found for this exercise.")

    return analysis


@router.get("/exercises/{exercise_name}/trend")
def exercise_trend(exercise_name: str):
    return get_exercise_trend(exercise_name)


@router.get("/exercises/{exercise_name}/progression")
def exercise_progression(exercise_name: str):
    return get_progression_recommendation(exercise_name)


@router.get("/exercises/{exercise_name}/last")
def exercise_last(exercise_name: str):
    analysis = get_exercise_analysis(exercise_name)

    if analysis is None:
        raise HTTPException(status_code=404, detail="No workout found for this exercise.")

    return analysis


@router.get("/volume/weekly")
def weekly_volume(weeks_back: int = 0):
    return get_weekly_training_volume(weeks_back=weeks_back)
