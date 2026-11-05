from src.analytics import get_exercise_analysis, get_progression_recommendation


def round_to_five(weight):
    """
    Round a weight to the nearest 5 pounds.

    Most barbell prescriptions should use practical
    weights that can actually be loaded in the gym.
    """
    return round(weight / 5) * 5


def get_next_weight(exercise_name):
    """
    Use actual workout history and the progression engine
    to recommend the next training weight for an exercise.
    """

    # Newest entry from either the per-set log or the legacy table.
    last_workout = get_exercise_analysis(exercise_name)

    if last_workout is None:
        return {
            "exercise": exercise_name,
            "decision": "NO_HISTORY",
            "previous_weight": None,
            "recommended_weight": None,
            "reason": "No previous workout found.",
        }

    progression = get_progression_recommendation(
        exercise_name
    )

    current_weight = last_workout["weight"]
    decision = progression["decision"]

    if current_weight is None:
        recommended_weight = None

    elif decision == "INCREASE":
        recommended_weight = round_to_five(
            current_weight + 5
        )

    elif decision == "HOLD":
        recommended_weight = current_weight

    elif decision == "REDUCE":
        recommended_weight = round_to_five(
            current_weight * 0.90
        )

    else:
        recommended_weight = current_weight

    return {
        "exercise": exercise_name,
        "decision": decision,
        "previous_weight": current_weight,
        "recommended_weight": recommended_weight,
        "reason": progression["reason"],
    }

def get_strength_template():
    """
    Return the base structure for the four lifting days.

    This defines WHAT we train.
    It does not decide progression from workout history.
    """

    return {
        "lower_strength": [
            {
                "exercise": "Back Squat",
                "sets": 3,
                "reps": 5,
                "rest": "2-3 min",
                "target_rpe": 8,
                "use_progression": True,
            },
            {
                "exercise": "Romanian Deadlift",
                "sets": 3,
                "reps": 8,
                "rest": "90 sec",
                "target_rpe": 7,
                "use_progression": True,
            },
            {
                "exercise": "Bulgarian Split Squat",
                "sets": 2,
                "reps": 8,
                "rest": "60-90 sec",
                "target_rpe": 8,
                "use_progression": True,
            },
        ],

        "upper_strength": [
            {
                "exercise": "Bench Press",
                "sets": 3,
                "reps": 5,
                "rest": "2-3 min",
                "target_rpe": 8,
                "use_progression": True,
            },
            {
                "exercise": "Pull-Ups",
                "sets": 4,
                "reps": 4,
                "rest": "2 min",
                "target_rpe": 8,
                "use_progression": False,
            },
            {
                "exercise": "Barbell Row",
                "sets": 3,
                "reps": 8,
                "rest": "90 sec",
                "target_rpe": 8,
                "use_progression": True,
            },
        ],

        "lower_power": [
            {
                "exercise": "Speed Squat",
                "sets": 5,
                "reps": 3,
                "rest": "60-90 sec",
                "target_rpe": 6,
                "use_progression": False,
            },
            {
                "exercise": "Pogo Jumps",
                "sets": 3,
                "reps": 20,
                "rest": "45 sec",
                "target_rpe": 5,
                "use_progression": False,
            },
            {
                "exercise": "Skater Bounds",
                "sets": 3,
                "reps": 5,
                "rest": "60 sec",
                "target_rpe": 6,
                "use_progression": False,
            },
        ],

        "upper_power": [
            {
                "exercise": "Push Press",
                "sets": 4,
                "reps": 3,
                "rest": "90 sec",
                "target_rpe": 7,
                "use_progression": False,
            },
            {
                "exercise": "Speed Bench Press",
                "sets": 6,
                "reps": 3,
                "rest": "60 sec",
                "target_rpe": 6,
                "use_progression": False,
            },
            {
                "exercise": "Pull-Ups",
                "sets": 4,
                "reps": 4,
                "rest": "2 min",
                "target_rpe": 8,
                "use_progression": False,
            },
        ],
    }

def build_strength_plan():
    """
    Build the strength portion of the weekly plan.

    Exercises that use progression receive a weight
    recommendation based on actual database history.

    Exercises without progression keep their weight
    unset for now.
    """

    template = get_strength_template()

    strength_plan = {}

    for day_name, exercises in template.items():

        strength_plan[day_name] = []

        for exercise in exercises:

            planned_exercise = exercise.copy()

            if exercise["use_progression"]:

                recommendation = get_next_weight(
                    exercise["exercise"]
                )

                planned_exercise["weight"] = (
                    recommendation["recommended_weight"]
                )

                planned_exercise["progression_decision"] = (
                    recommendation["decision"]
                )

                planned_exercise["progression_reason"] = (
                    recommendation["reason"]
                )

            else:

                planned_exercise["weight"] = None

                planned_exercise["progression_decision"] = (
                    "NOT_APPLICABLE"
                )

                planned_exercise["progression_reason"] = (
                    "This exercise does not use the "
                    "standard load progression system."
                )

            strength_plan[day_name].append(
                planned_exercise
            )

    return strength_plan
def build_weekly_plan(week_dates):
    """
    Build the complete seven-day training plan.

    This combines the strength plan with the weekly
    schedule and athletic/running sessions.

    The returned dictionary matches the structure
    expected by excel_generator.py.
    """

    strength_plan = build_strength_plan()

    overview = [
        {
            "date": week_dates[0],
            "focus": "Lower Body Strength",
            "goal": "Build lower-body strength",
        },
        {
            "date": week_dates[1],
            "focus": "Upper Body Strength",
            "goal": "Build pressing and pulling strength",
        },
        {
            "date": week_dates[2],
            "focus": "Recovery / Running",
            "goal": "Aerobic conditioning and recovery",
        },
        {
            "date": week_dates[3],
            "focus": "Lower Body Power",
            "goal": "Explosiveness and lateral movement",
        },
        {
            "date": week_dates[4],
            "focus": "Upper Body Power",
            "goal": "Upper-body speed and power",
        },
        {
            "date": week_dates[5],
            "focus": "Running / Athleticism",
            "goal": "Speed and conditioning",
        },
        {
            "date": week_dates[6],
            "focus": "Recovery",
            "goal": "Prepare for the next training week",
        },
    ]

    day_mapping = {
        "lower_strength": week_dates[0],
        "upper_strength": week_dates[1],
        "lower_power": week_dates[3],
        "upper_power": week_dates[4],
    }

    strength = []

    for day_name, exercises in strength_plan.items():

        workout_date = day_mapping[day_name]

        for exercise in exercises:

            strength.append({
                "date": workout_date,
                "exercise": exercise["exercise"],
                "weight": exercise["weight"],
                "sets": exercise["sets"],
                "reps": exercise["reps"],
                "rest": exercise["rest"],
                "target_rpe": exercise["target_rpe"],
            })

    running = [
        {
            "date": week_dates[2],
            "session_type": "Easy Run",
            "planned_work": "2 miles",
            "target": "Controlled aerobic pace",
        },
        {
            "date": week_dates[3],
            "session_type": "Plyometrics / Agility",
            "planned_work": "Pogos + skater bounds",
            "target": "High-quality explosive reps",
        },
        {
            "date": week_dates[5],
            "session_type": "Speed",
            "planned_work": "Short acceleration work",
            "target": "Fast first step, full recovery",
        },
    ]

    return {
        "overview": overview,
        "strength": strength,
        "running": running,
    }
if __name__ == "__main__":
    from datetime import date, timedelta

    today = date.today()

    monday = today - timedelta(
        days=today.weekday()
    )

    week_dates = [
        monday + timedelta(days=i)
        for i in range(7)
    ]

    plan = build_weekly_plan(
        week_dates
    )

    print("\nWEEKLY OVERVIEW")

    for day in plan["overview"]:
        print(
            day["date"],
            "|",
            day["focus"],
        )

    print("\nSTRENGTH PLAN")

    for exercise in plan["strength"]:
        print(
            exercise["date"],
            "|",
            exercise["exercise"],
            "|",
            exercise["sets"],
            "x",
            exercise["reps"],
            "| Weight:",
            exercise["weight"],
        )

    print("\nRUNNING / ATHLETICISM")

    for session in plan["running"]:
        print(
            session["date"],
            "|",
            session["session_type"],
            "|",
            session["planned_work"],
        )