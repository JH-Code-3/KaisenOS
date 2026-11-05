from pathlib import Path
from datetime import date
import json
from src.excel_generator import build_weekly_workbook

from src import local_llm
from backend.config import load_settings
from pypdf import PdfReader

from src.database import (
    create_database,
    get_workouts,
    get_last_exercise,
    add_workout,
    add_body_metric,
    get_body_metrics,
    add_recovery,
    get_recovery,
    add_run,
    get_runs,
    add_nutrition,
    get_nutrition,
)

from src.analytics import (
    get_exercise_analysis,
    get_exercise_trend,
    get_latest_run_analysis,
    get_run_trend,
    get_body_weight_trend,
    get_progression_recommendation,
)


PROJECT_ROOT = Path(__file__).resolve().parent

PDF_PATH = PROJECT_ROOT / (
    "knowledge/90_Day_Athletic_Body_Transformation_AI_Coach_Blueprint.pdf"
)

# Change the model in Settings (dashboard) or data/settings.json -> "ollama_model".
MODEL_NAME = load_settings()["ollama_model"]


# ==================================================
# PDF / BLUEPRINT
# ==================================================

def read_pdf(path):
    # Optional: drop your own training-reference PDF into knowledge/. Without one,
    # the coach just works from your logs.
    if not Path(path).is_file():
        return ""
    reader = PdfReader(path)
    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages)


# ==================================================
# HELPERS
# ==================================================

def today_string():
    return date.today().isoformat()


def format_rows(rows):
    if not rows:
        return "No records found."

    return "\n".join(str(row) for row in rows)


# ==================================================
# DATABASE READ TOOLS
# ==================================================

def get_last_exercise_tool(exercise_name: str) -> str:
    workout = get_last_exercise(exercise_name)

    if not workout:
        return f"No workout found for {exercise_name}."

    (
        workout_date,
        exercise,
        weight,
        sets,
        reps,
        rpe,
        pain,
        notes,
    ) = workout

    return (
        f"Date: {workout_date} | "
        f"Exercise: {exercise} | "
        f"Weight: {weight} lb | "
        f"Sets: {sets} | "
        f"Reps: {reps} | "
        f"RPE: {rpe} | "
        f"Pain: {pain} | "
        f"Notes: {notes}"
    )


def get_workouts_tool(limit: int = 10) -> str:
    workouts = get_workouts()

    return format_rows(workouts[:limit])


def get_body_metrics_tool(limit: int = 10) -> str:
    metrics = get_body_metrics()

    return format_rows(metrics[:limit])


def get_recovery_tool(limit: int = 10) -> str:
    records = get_recovery()

    return format_rows(records[:limit])


def get_runs_tool(limit: int = 10) -> str:
    runs = get_runs()

    return format_rows(runs[:limit])


def get_nutrition_tool(limit: int = 10) -> str:
    records = get_nutrition()

    return format_rows(records[:limit])


# ==================================================
# CONTROLLED DATABASE WRITE TOOLS
# ==================================================

def add_workout_tool(
    workout_date: str = None,
    exercise: str = None,
    weight: float = None,
    sets: int = None,
    reps: int = None,
    rpe: float = None,
    pain: float = None,
    notes: str = None,
) -> str:

    required_fields = {
        "workout_date": workout_date,
        "exercise": exercise,
        "weight": weight,
        "sets": sets,
        "reps": reps,
        "rpe": rpe,
        "pain": pain,
        "notes": notes,
    }

    missing = []

    for field_name, value in required_fields.items():
        if value is None or value == "":
            missing.append(field_name)

    if missing:
        return (
            "SAVE REJECTED. "
            f"Missing required fields: {', '.join(missing)}. "
            "No database record was created."
        )

    add_workout(
        workout_date,
        exercise,
        weight,
        sets,
        reps,
        rpe,
        pain,
        notes,
    )

    return (
        "SAVE SUCCESSFUL. "
        f"{workout_date} | "
        f"{exercise} | "
        f"{weight} lb | "
        f"{sets} set(s) x {reps} reps | "
        f"RPE {rpe} | "
        f"Pain {pain} | "
        f"Notes: {notes}"
    )


def add_body_metric_tool(
    metric_date: str = None,
    body_weight: float = None,
    body_fat: float = None,
    waist: float = None,
    notes: str = None,
) -> str:

    if metric_date is None:
        return "SAVE REJECTED. Missing metric_date."

    if (
        body_weight is None
        and body_fat is None
        and waist is None
    ):
        return (
            "SAVE REJECTED. "
            "At least one body metric is required."
        )

    add_body_metric(
        metric_date,
        body_weight,
        body_fat,
        waist,
        notes,
    )

    return (
        "SAVE SUCCESSFUL. "
        f"{metric_date} | "
        f"Weight: {body_weight} | "
        f"Body Fat: {body_fat} | "
        f"Waist: {waist} | "
        f"Notes: {notes}"
    )


def add_recovery_tool(
    recovery_date: str = None,
    sleep_hours: float = None,
    energy: float = None,
    soreness: float = None,
    pain: float = None,
    notes: str = None,
) -> str:

    if recovery_date is None:
        return "SAVE REJECTED. Missing recovery_date."

    if (
        sleep_hours is None
        and energy is None
        and soreness is None
        and pain is None
    ):
        return (
            "SAVE REJECTED. "
            "At least one recovery measurement is required."
        )

    add_recovery(
        recovery_date,
        sleep_hours,
        energy,
        soreness,
        pain,
        notes,
    )

    return (
        "SAVE SUCCESSFUL. "
        f"{recovery_date} | "
        f"Sleep: {sleep_hours} hours | "
        f"Energy: {energy} | "
        f"Soreness: {soreness} | "
        f"Pain: {pain} | "
        f"Notes: {notes}"
    )


def add_run_tool(
    run_date: str = None,
    distance_miles: float = None,
    duration_minutes: float = None,
    pace_per_mile: float = None,
    rpe: float = None,
    notes: str = None,
) -> str:

    if run_date is None:
        return "SAVE REJECTED. Missing run_date."

    if (
        distance_miles is None
        and duration_minutes is None
        and pace_per_mile is None
    ):
        return (
            "SAVE REJECTED. "
            "At least one running measurement is required."
        )

    add_run(
        run_date,
        distance_miles,
        duration_minutes,
        pace_per_mile,
        rpe,
        notes,
    )

    return (
        "SAVE SUCCESSFUL. "
        f"{run_date} | "
        f"Distance: {distance_miles} miles | "
        f"Duration: {duration_minutes} minutes | "
        f"Pace: {pace_per_mile} min/mile | "
        f"RPE: {rpe} | "
        f"Notes: {notes}"
    )


def add_nutrition_tool(
    nutrition_date: str = None,
    calories: float = None,
    protein_g: float = None,
    carbs_g: float = None,
    fat_g: float = None,
    notes: str = None,
) -> str:

    if nutrition_date is None:
        return "SAVE REJECTED. Missing nutrition_date."

    if (
        calories is None
        and protein_g is None
        and carbs_g is None
        and fat_g is None
    ):
        return (
            "SAVE REJECTED. "
            "At least one nutrition measurement is required."
        )

    add_nutrition(
        nutrition_date,
        calories,
        protein_g,
        carbs_g,
        fat_g,
        notes,
    )

    return (
        "SAVE SUCCESSFUL. "
        f"{nutrition_date} | "
        f"Calories: {calories} | "
        f"Protein: {protein_g} g | "
        f"Carbs: {carbs_g} g | "
        f"Fat: {fat_g} g | "
        f"Notes: {notes}"
    )


# ==================================================
# PENDING STATES
# ==================================================

def new_pending_workout():
    return {
        "workout_date": None,
        "exercise": None,
        "weight": None,
        "sets": None,
        "reps": None,
        "rpe": None,
        "pain": None,
        "notes": None,
    }


def new_pending_body_metric():
    return {
        "metric_date": None,
        "body_weight": None,
        "body_fat": None,
        "waist": None,
        "notes": None,
    }


def new_pending_recovery():
    return {
        "recovery_date": None,
        "sleep_hours": None,
        "energy": None,
        "soreness": None,
        "pain": None,
        "notes": None,
    }


def new_pending_run():
    return {
        "run_date": None,
        "distance_miles": None,
        "duration_minutes": None,
        "pace_per_mile": None,
        "rpe": None,
        "notes": None,
    }


def new_pending_nutrition():
    return {
        "nutrition_date": None,
        "calories": None,
        "protein_g": None,
        "carbs_g": None,
        "fat_g": None,
        "notes": None,
    }


# ==================================================
# JSON EXTRACTION
# ==================================================

def extract_json(user_text, current_data, instructions):
    prompt = f"""
You are a structured data extraction system.

Today's date is {today_string()}.

CURRENT PENDING DATA:
{json.dumps(current_data, indent=2)}

TASK RULES:
{instructions}

GENERAL RULES:
- Preserve values already present in CURRENT PENDING DATA.
- Change an existing value only if the user clearly corrects it.
- Never guess missing information.
- Missing information must be null.
- Numbers must be JSON numbers.
- Return JSON only.
- Do not include markdown.
- Do not explain your answer.
"""

    response = local_llm.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": user_text,
            },
        ],
        format="json",
        think="low",
        options={
            "num_predict": 512,
        },
    )

    try:
        extracted = json.loads(
            response.message.content
        )

    except json.JSONDecodeError:
        return current_data

    updated = current_data.copy()

    for field in updated:
        value = extracted.get(field)

        if value is not None and value != "":
            updated[field] = value

    return updated


# ==================================================
# CATEGORY EXTRACTORS
# ==================================================

def extract_workout(user_text, current_data):
    instructions = f"""
Use exactly these keys:

workout_date
exercise
weight
sets
reps
rpe
pain
notes

Rules:
- If the user says today, workout_date="{today_string()}".
- "155 pounds for 5 reps" means weight=155 and reps=5.
- It does NOT mean sets=1.
- Normalize bench to Bench Press.
- Normalize back squat to Back Squat.
- Normalize deadlift to Deadlift unless clearly specified otherwise.
- Pain is numeric 0-10.
- RPE is numeric.
- Notes contain only notes explicitly provided.
"""

    return extract_json(
        user_text,
        current_data,
        instructions,
    )


def extract_body_metric(user_text, current_data):
    instructions = f"""
Use exactly these keys:

metric_date
body_weight
body_fat
waist
notes

Rules:
- If the user says today, metric_date="{today_string()}".
- Weight means body_weight.
- Body weight is in pounds unless explicitly stated otherwise.
- body_fat is a numeric percentage.
- waist is numeric inches unless explicitly stated otherwise.
- Do not invent body fat or waist from weight.
"""

    return extract_json(
        user_text,
        current_data,
        instructions,
    )


def extract_recovery(user_text, current_data):
    instructions = f"""
Use exactly these keys:

recovery_date
sleep_hours
energy
soreness
pain
notes

Rules:
- If the user says today, recovery_date="{today_string()}".
- Sleep is measured in hours.
- Energy is numeric.
- Soreness is numeric.
- Pain is numeric 0-10.
- Do not infer missing measurements.
"""

    return extract_json(
        user_text,
        current_data,
        instructions,
    )


def extract_run(user_text, current_data):
    instructions = f"""
Use exactly these keys:

run_date
distance_miles
duration_minutes
pace_per_mile
rpe
notes

Rules:
- If the user says today, run_date="{today_string()}".
- distance_miles is numeric miles.
- duration_minutes is total numeric minutes.
- pace_per_mile is minutes per mile.
- Do not calculate pace unless explicitly given.
- RPE is numeric.
"""

    return extract_json(
        user_text,
        current_data,
        instructions,
    )


def extract_nutrition(user_text, current_data):
    instructions = f"""
Use exactly these keys:

nutrition_date
calories
protein_g
carbs_g
fat_g
notes

Rules:
- If the user says today, nutrition_date="{today_string()}".
- calories means total calories.
- protein means grams of protein.
- carbs means grams of carbohydrates.
- fat means grams of fat.
- Do not calculate missing macros.
"""

    return extract_json(
        user_text,
        current_data,
        instructions,
    )


# ==================================================
# LOG DETECTION
# ==================================================

def detect_log_type(user_text):
    text = user_text.lower()

    logging_words = [
        "log",
        "record",
        "save",
    ]

    if not any(word in text for word in logging_words):
        return None

    body_terms = [
        "body weight",
        "my weight",
        "body fat",
        "waist",
    ]

    recovery_terms = [
        "recovery",
        "sleep",
        "soreness",
        "energy",
        "readiness",
    ]

    running_terms = [
        "run",
        "running",
        "mile",
        "sprint",
    ]

    nutrition_terms = [
        "nutrition",
        "calories",
        "protein",
        "carbs",
        "fat",
        "macros",
    ]

    workout_terms = [
        "workout",
        "bench",
        "squat",
        "deadlift",
        "press",
        "row",
        "pull-up",
        "pullup",
        "curl",
        "lunge",
        "rdl",
    ]

    if any(term in text for term in body_terms):
        return "body"

    if any(term in text for term in recovery_terms):
        return "recovery"

    if any(term in text for term in running_terms):
        return "running"

    if any(term in text for term in nutrition_terms):
        return "nutrition"

    if any(term in text for term in workout_terms):
        return "workout"

    return None


# ==================================================
# READ DETECTION
# ==================================================

def detect_read_type(user_text):
    text = user_text.lower()

    read_words = [
        "latest",
        "last",
        "recent",
        "history",
        "what did",
        "what was",
        "show me",
        "how much",
        "what is my",
        "what's my",
        "whats my",
    ]

    if not any(word in text for word in read_words):
        return None

    if "recovery" in text or "sleep" in text:
        return "recovery"

    if (
        "body weight" in text
        or "my weight" in text
        or "body fat" in text
        or "waist" in text
    ):
        return "body"

    if (
        "run" in text
        or "running" in text
        or "mile" in text
    ):
        return "running"

    if (
        "nutrition" in text
        or "calories" in text
        or "protein" in text
        or "carbs" in text
        or "macros" in text
    ):
        return "nutrition"

    if (
        "bench" in text
        or "squat" in text
        or "deadlift" in text
        or "workout" in text
    ):
        return "workout"

    return None
def detect_analytics_type(user_text):
    text = user_text.lower()

    # ----------------------------------------------
    # PROGRESSION QUESTIONS
    # ----------------------------------------------

    progression_terms = [
        "should i increase",
        "should i go up",
        "increase my",
        "go up on",
        "progression",
        "progress my",
        "next weight",
        "next time",
    ]

    if any(term in text for term in progression_terms):

        if "bench" in text:
            return (
                "progression",
                "Bench Press",
            )

        if "squat" in text:
            return (
                "progression",
                "Back Squat",
            )

        if "deadlift" in text:
            return (
                "progression",
                "Deadlift",
            )

    # ----------------------------------------------
    # ESTIMATED 1RM
    # ----------------------------------------------

    e1rm_terms = [
        "estimate",
        "estimated",
        "estimates",
        "e1rm",
        "1rm",
        "one rep max",
        "max",
    ]

    if any(term in text for term in e1rm_terms):

        if "bench" in text:
            return (
                "exercise_analysis",
                "Bench Press",
            )

        if "squat" in text:
            return (
                "exercise_analysis",
                "Back Squat",
            )

        if "deadlift" in text:
            return (
                "exercise_analysis",
                "Deadlift",
            )

    # ----------------------------------------------
    # TRENDS
    # ----------------------------------------------

    trend_terms = [
        "improving",
        "progressing",
        "trend",
        "trending",
        "getting stronger",
        "stronger",
        "faster",
        "slower",
    ]

    if any(term in text for term in trend_terms):

        if "bench" in text:
            return (
                "exercise_trend",
                "Bench Press",
            )

        if "squat" in text:
            return (
                "exercise_trend",
                "Back Squat",
            )

        if "deadlift" in text:
            return (
                "exercise_trend",
                "Deadlift",
            )

    # ----------------------------------------------
    # BODY-WEIGHT TREND
    # ----------------------------------------------

    if (
        any(term in text for term in trend_terms)
        and (
            "body weight" in text
            or "my weight" in text
            or "weight trending" in text
        )
    ):
        return (
            "body_weight_trend",
            None,
        )

    # ----------------------------------------------
    # RUNNING TREND
    # ----------------------------------------------

    if (
        any(term in text for term in trend_terms)
        and (
            "run" in text
            or "running" in text
            or "pace" in text
        )
    ):
        return (
            "run_trend",
            None,
        )

    # ----------------------------------------------
    # LATEST RUNNING PACE
    # ----------------------------------------------

    if (
        "pace" in text
        and (
            "run" in text
            or "running" in text
            or "mile" in text
        )
    ):
        return (
            "run_analysis",
            None,
        )

    return None

def detect_plan_request(user_text):
    """
    Detect whether the user wants a weekly workout
    workbook generated.
    """

    text = user_text.lower()

    action_terms = [
        "generate",
        "create",
        "make",
        "build",
    ]

    plan_terms = [
        "weekly plan",
        "workout plan",
        "training plan",
        "weekly workout",
        "workout week",
    ]

    has_action = any(
        term in text
        for term in action_terms
    )

    has_plan = any(
        term in text
        for term in plan_terms
    )

    return has_action and has_plan

# ==================================================
# DISPLAY PENDING DATA
# ==================================================

def show_pending(data):
    lines = []

    for field, value in data.items():
        if value is not None and value != "":
            lines.append(
                f"- {field}: {value}"
            )

    if not lines:
        return "No information collected yet."

    return "\n".join(lines)


# ==================================================
# INITIALIZE
# ==================================================

blueprint = read_pdf(PDF_PATH)

from src.paths import make_private

make_private()
create_database()


system_prompt = f"""
You are a local AI strength and conditioning coach.

Your job is to help the athlete with:
- strength
- athletic performance
- running
- sprinting
- recovery
- nutrition
- body composition
- progression planning

DATABASE RULES:
- SQLite is the source of truth for completed data.
- Never invent logged history.
- Never claim something was saved unless Python returns SAVE SUCCESSFUL.
- Planned workouts are not completed workouts.
- If database information conflicts with conversational memory,
  trust the database.

ANALYTICS RULES:
- Deterministic Python calculations are the source of truth for
  e1RM, training volume, running pace, and trends.
- Do not invent trends when there is not enough data.
- Consider RPE, pain, recovery, and performance when discussing progression.

--- MASTER COACH BLUEPRINT ---

{blueprint}

--- END MASTER COACH BLUEPRINT ---
"""


messages = [
    {
        "role": "system",
        "content": system_prompt,
    }
]


tools = [
    get_last_exercise_tool,
    get_workouts_tool,
    get_body_metrics_tool,
    get_recovery_tool,
    get_runs_tool,
    get_nutrition_tool,
]


read_tool_map = {
    "get_last_exercise_tool":
        get_last_exercise_tool,

    "get_workouts_tool":
        get_workouts_tool,

    "get_body_metrics_tool":
        get_body_metrics_tool,

    "get_recovery_tool":
        get_recovery_tool,

    "get_runs_tool":
        get_runs_tool,

    "get_nutrition_tool":
        get_nutrition_tool,
}


pending_workout = new_pending_workout()
pending_body_metric = new_pending_body_metric()
pending_recovery = new_pending_recovery()
pending_run = new_pending_run()
pending_nutrition = new_pending_nutrition()

active_log_type = None


# ==================================================
# START
# ==================================================

print("KaisenOS — local AI coach")

# Startup check: Ollama must be on localhost and the model downloaded locally.
try:
    local_llm.check_model(MODEL_NAME)
except local_llm.LocalLLMError as startup_error:
    print(f"\nCan't start the coach: {startup_error}")
    raise SystemExit(1)

print(f"Using local model {MODEL_NAME} via http://localhost:11434")
print("Type 'quit' to exit.")
print("Type 'cancel log' to cancel an active log.\n")


# ==================================================
# MAIN LOOP
# ==================================================

while True:

    user_input = input("You: ")
    user_lower = user_input.lower().strip()

    # ----------------------------------------------
    # EXIT
    # ----------------------------------------------

    if user_lower in [
        "quit",
        "exit",
    ]:
        print("\nCoach: Session ended.")
        break

    # ----------------------------------------------
    # CANCEL LOG
    # ----------------------------------------------

    if user_lower == "cancel log":

        pending_workout = new_pending_workout()
        pending_body_metric = new_pending_body_metric()
        pending_recovery = new_pending_recovery()
        pending_run = new_pending_run()
        pending_nutrition = new_pending_nutrition()

        active_log_type = None

        print(
            "\nCoach: Pending log canceled.\n"
        )

        continue

    # ----------------------------------------------
    # DETECT LOG REQUEST
    # ----------------------------------------------

    detected_type = detect_log_type(
        user_input
    )

    if detected_type is not None:
        active_log_type = detected_type

    # ==================================================
    # WORKOUT LOGGING
    # ==================================================

    if active_log_type == "workout":

        pending_workout = extract_workout(
            user_input,
            pending_workout,
        )

        missing = []

        for field, value in pending_workout.items():
            if value is None or value == "":
                missing.append(field)

        if missing:

            print(
                "\nCoach: I have this so far:\n"
            )

            print(
                show_pending(
                    pending_workout
                )
            )

            print("\nI still need:")

            for field in missing:
                print(f"- {field}")

            print(
                "\nGive me the missing information, "
                "or type 'cancel log'.\n"
            )

            continue

        result = add_workout_tool(
            **pending_workout
        )

        print(
            f"\nCoach: {result}\n"
        )

        pending_workout = new_pending_workout()
        active_log_type = None

        continue

    # ==================================================
    # BODY METRIC LOGGING
    # ==================================================

    if active_log_type == "body":

        pending_body_metric = extract_body_metric(
            user_input,
            pending_body_metric,
        )

        has_metric = (
            pending_body_metric[
                "body_weight"
            ] is not None
            or pending_body_metric[
                "body_fat"
            ] is not None
            or pending_body_metric[
                "waist"
            ] is not None
        )

        missing = []

        if (
            pending_body_metric[
                "metric_date"
            ] is None
        ):
            missing.append(
                "metric_date"
            )

        if not has_metric:
            missing.append(
                "body_weight, body_fat, or waist"
            )

        if missing:

            print(
                "\nCoach: I have this so far:\n"
            )

            print(
                show_pending(
                    pending_body_metric
                )
            )

            print("\nI still need:")

            for field in missing:
                print(f"- {field}")

            print(
                "\nGive me the missing information, "
                "or type 'cancel log'.\n"
            )

            continue

        result = add_body_metric_tool(
            **pending_body_metric
        )

        print(
            f"\nCoach: {result}\n"
        )

        pending_body_metric = new_pending_body_metric()
        active_log_type = None

        continue

    # ==================================================
    # RECOVERY LOGGING
    # ==================================================

    if active_log_type == "recovery":

        pending_recovery = extract_recovery(
            user_input,
            pending_recovery,
        )

        has_measurement = (
            pending_recovery[
                "sleep_hours"
            ] is not None
            or pending_recovery[
                "energy"
            ] is not None
            or pending_recovery[
                "soreness"
            ] is not None
            or pending_recovery[
                "pain"
            ] is not None
        )

        missing = []

        if (
            pending_recovery[
                "recovery_date"
            ] is None
        ):
            missing.append(
                "recovery_date"
            )

        if not has_measurement:
            missing.append(
                "at least one recovery measurement"
            )

        if missing:

            print(
                "\nCoach: I have this so far:\n"
            )

            print(
                show_pending(
                    pending_recovery
                )
            )

            print("\nI still need:")

            for field in missing:
                print(f"- {field}")

            print(
                "\nGive me the missing information, "
                "or type 'cancel log'.\n"
            )

            continue

        result = add_recovery_tool(
            **pending_recovery
        )

        print(
            f"\nCoach: {result}\n"
        )

        pending_recovery = new_pending_recovery()
        active_log_type = None

        continue

    # ==================================================
    # RUNNING LOGGING
    # ==================================================

    if active_log_type == "running":

        pending_run = extract_run(
            user_input,
            pending_run,
        )

        has_measurement = (
            pending_run[
                "distance_miles"
            ] is not None
            or pending_run[
                "duration_minutes"
            ] is not None
            or pending_run[
                "pace_per_mile"
            ] is not None
        )

        missing = []

        if (
            pending_run[
                "run_date"
            ] is None
        ):
            missing.append(
                "run_date"
            )

        if not has_measurement:
            missing.append(
                "distance, duration, or pace"
            )

        if missing:

            print(
                "\nCoach: I have this so far:\n"
            )

            print(
                show_pending(
                    pending_run
                )
            )

            print("\nI still need:")

            for field in missing:
                print(f"- {field}")

            print(
                "\nGive me the missing information, "
                "or type 'cancel log'.\n"
            )

            continue

        result = add_run_tool(
            **pending_run
        )

        print(
            f"\nCoach: {result}\n"
        )

        pending_run = new_pending_run()
        active_log_type = None

        continue

    # ==================================================
    # NUTRITION LOGGING
    # ==================================================

    if active_log_type == "nutrition":

        pending_nutrition = extract_nutrition(
            user_input,
            pending_nutrition,
        )

        has_measurement = (
            pending_nutrition[
                "calories"
            ] is not None
            or pending_nutrition[
                "protein_g"
            ] is not None
            or pending_nutrition[
                "carbs_g"
            ] is not None
            or pending_nutrition[
                "fat_g"
            ] is not None
        )

        missing = []

        if (
            pending_nutrition[
                "nutrition_date"
            ] is None
        ):
            missing.append(
                "nutrition_date"
            )

        if not has_measurement:
            missing.append(
                "calories or at least one macro"
            )

        if missing:

            print(
                "\nCoach: I have this so far:\n"
            )

            print(
                show_pending(
                    pending_nutrition
                )
            )

            print("\nI still need:")

            for field in missing:
                print(f"- {field}")

            print(
                "\nGive me the missing information, "
                "or type 'cancel log'.\n"
            )

            continue

        result = add_nutrition_tool(
            **pending_nutrition
        )

        print(
            f"\nCoach: {result}\n"
        )

        pending_nutrition = new_pending_nutrition()
        active_log_type = None

        continue

    # ==================================================
    # DETERMINISTIC ANALYTICS
    # ==================================================

    analytics_request = detect_analytics_type(
        user_input
    )

    if analytics_request is not None:

        analytics_type, exercise_name = (
            analytics_request
        )
        if analytics_type == "progression":

            result = get_progression_recommendation(
                exercise_name
            )

            print(
                f"\nCoach: {result}\n"
            )

            continue

        if analytics_type == "exercise_analysis":

            result = get_exercise_analysis(
                exercise_name
            )

            print(
                f"\nCoach: {result}\n"
            )

            continue

        if analytics_type == "exercise_trend":

            result = get_exercise_trend(
                exercise_name
            )

            print(
                f"\nCoach: {result}\n"
            )

            continue

        if analytics_type == "run_analysis":

            result = get_latest_run_analysis()

            print(
                f"\nCoach: {result}\n"
            )

            continue

        if analytics_type == "run_trend":

            result = get_run_trend()

            print(
                f"\nCoach: {result}\n"
            )

            continue

        if analytics_type == "body_weight_trend":

            result = get_body_weight_trend()

            print(
                f"\nCoach: {result}\n"
            )

            continue

    # ==================================================
    # DETERMINISTIC DATABASE READS
    # ==================================================

    read_type = detect_read_type(
        user_input
    )

    if read_type == "recovery":

        result = get_recovery_tool(
            limit=1
        )

        print(
            f"\nCoach: {result}\n"
        )

        continue

    if read_type == "body":

        result = get_body_metrics_tool(
            limit=1
        )

        print(
            f"\nCoach: {result}\n"
        )

        continue

    if read_type == "running":

        result = get_runs_tool(
            limit=1
        )

        print(
            f"\nCoach: {result}\n"
        )

        continue

    if read_type == "nutrition":

        result = get_nutrition_tool(
            limit=1
        )

        print(
            f"\nCoach: {result}\n"
        )

        continue

    if read_type == "workout":

        result = get_workouts_tool(
            limit=5
        )

        print(
            f"\nCoach: {result}\n"
        )

        continue
    # ==================================================
    # WEEKLY PLAN GENERATION
    # ==================================================

    if detect_plan_request(user_input):

        try:
            path = build_weekly_workbook(
                week_number=1
            )

            print(
                "\nCoach: Weekly workout plan created successfully.\n"
                f"File: {path}\n"
            )

        except Exception as error:
            print(
                "\nCoach: I could not create the weekly plan.\n"
                f"Error: {error}\n"
            )

        continue
    # ==================================================
    # NORMAL AI COACH CONVERSATION
    # ==================================================

    messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    response = local_llm.chat(
        model=MODEL_NAME,
        messages=messages,
        tools=tools,
        think="low",
        options={
            "num_predict": 2048,
        },
    )

    messages.append(
        response.message
    )

    # ----------------------------------------------
    # TOOL CALLS
    # ----------------------------------------------

    if response.message.tool_calls:

        for call in response.message.tool_calls:

            function_name = (
                call.function.name
            )

            function = read_tool_map.get(
                function_name
            )

            if function is None:
                result = (
                    "Unknown database tool."
                )

            else:

                try:
                    result = function(
                        **call.function.arguments
                    )

                except Exception as error:
                    result = (
                        "Database tool error: "
                        f"{error}"
                    )

            messages.append(
                {
                    "role": "tool",
                    "tool_name":
                        function_name,
                    "content":
                        str(result),
                }
            )

        final_response = local_llm.chat(
            model=MODEL_NAME,
            messages=messages,
            tools=tools,
            think="low",
            options={
                "num_predict": 2048,
            },
        )

        coach_reply = (
            final_response.message.content
        )

        messages.append(
            final_response.message
        )

    else:

        coach_reply = (
            response.message.content
        )

    print(
        f"\nCoach: {coach_reply}\n"
    )