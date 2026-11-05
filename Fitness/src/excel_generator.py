from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

from src.weekly_planner import build_weekly_plan


# ==================================================
# FILE LOCATION
# ==================================================

# Weekly workbooks will be saved inside:
#
# Fitness/
# └── workouts/
#
# Anchored to the project root rather than CWD so this still works
# when called from a FastAPI backend running from a different directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
from src.paths import EXPORT_DIR  # noqa: E402  (exports are personal: kept with your data, not in the repo)

OUTPUT_DIR = EXPORT_DIR


# ==================================================
# COLORS / BASIC STYLING
# ==================================================

TITLE_FILL = "1F4E78"
HEADER_FILL = "D9EAF7"
WHITE = "FFFFFF"


# ==================================================
# DATE LOGIC
# ==================================================

def get_week_dates(start_date=None):
    """
    Return the Monday-Sunday dates for a week.

    If no date is supplied, Python uses today's date
    and finds the Monday of the current week.
    """

    if start_date is None:
        start_date = date.today()

    # weekday():
    # Monday = 0
    # Tuesday = 1
    # ...
    # Sunday = 6
    #
    # Subtracting that number takes us back to Monday.
    monday = start_date - timedelta(
        days=start_date.weekday()
    )

    week_dates = []

    for day_number in range(7):
        week_dates.append(
            monday + timedelta(days=day_number)
        )

    return week_dates


# ==================================================
# STYLE HELPERS
# ==================================================

def style_title(ws, cell_range, title):
    """
    Create the large blue title at the top
    of each worksheet.
    """

    ws.merge_cells(cell_range)

    first_cell = cell_range.split(":")[0]

    cell = ws[first_cell]
    cell.value = title

    cell.fill = PatternFill(
        fill_type="solid",
        fgColor=TITLE_FILL,
    )

    cell.font = Font(
        bold=True,
        color=WHITE,
        size=16,
    )

    cell.alignment = Alignment(
        horizontal="center",
        vertical="center",
    )


def style_header_row(ws, row_number, start_column, end_column):
    """
    Apply consistent formatting to table headers.
    """

    for row in ws.iter_rows(
        min_row=row_number,
        max_row=row_number,
        min_col=start_column,
        max_col=end_column,
    ):
        for cell in row:

            cell.fill = PatternFill(
                fill_type="solid",
                fgColor=HEADER_FILL,
            )

            cell.font = Font(
                bold=True
            )

            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True,
            )


# ==================================================
# WEEKLY OVERVIEW SHEET
# ==================================================

def create_overview_sheet(
    workbook,
    week_number,
    week_dates,
):
    """
    Create the Monday-Sunday overview sheet.

    This is the quick view of the entire training week.
    """

    ws = workbook.active
    ws.title = "Weekly Overview"

    style_title(
        ws,
        "A1:F1",
        f"AI Performance Coach - Week {week_number}",
    )

    headers = [
        "Day",
        "Date",
        "Training Focus",
        "Primary Goal",
        "Completed?",
        "Notes",
    ]

    ws.append([])
    ws.append(headers)

    style_header_row(
        ws,
        row_number=3,
        start_column=1,
        end_column=6,
    )

    for week_date in week_dates:

        ws.append([
            week_date.strftime("%A"),
            week_date,
            "",
            "",
            "No",
            "",
        ])

    # Format dates as normal Excel dates.
    for row in range(4, 11):
        ws.cell(
            row=row,
            column=2,
        ).number_format = "mm/dd/yyyy"

    # Create dropdown:
    # No / Yes / Partial
    completion_dropdown = DataValidation(
        type="list",
        formula1='"No,Yes,Partial"',
        allow_blank=True,
    )

    ws.add_data_validation(
        completion_dropdown
    )

    completion_dropdown.add(
        "E4:E10"
    )

    ws.freeze_panes = "A4"

    widths = {
        "A": 14,
        "B": 13,
        "C": 24,
        "D": 28,
        "E": 14,
        "F": 32,
    }

    for column, width in widths.items():
        ws.column_dimensions[column].width = width

    return ws


# ==================================================
# STRENGTH TRAINING SHEET
# ==================================================

def create_strength_sheet(
    workbook,
    week_number,
):
    """
    Create the detailed lifting log.

    Prescribed columns = what the AI coach planned.
    Actual columns = what the athlete really completed.

    This distinction is important because actual
    performance will later feed back into SQLite.
    """

    ws = workbook.create_sheet(
        "Strength Training"
    )

    style_title(
        ws,
        "A1:N1",
        f"Week {week_number} - Strength Training",
    )

    headers = [
        "Date",
        "Day",
        "Exercise",
        "Prescribed Weight",
        "Sets",
        "Reps",
        "Rest",
        "Target RPE",
        "Actual Weight",
        "Actual Sets",
        "Actual Reps",
        "Actual RPE",
        "Pain",
        "Notes",
    ]

    ws.append([])
    ws.append(headers)

    style_header_row(
        ws,
        row_number=3,
        start_column=1,
        end_column=14,
    )

    # Give us 35 empty training rows.
    # That is enough for about 5 exercises per day
    # across seven days.
    for _ in range(35):
        ws.append(
            [""] * 14
        )

    for row in range(4, 39):
        ws.cell(
            row=row,
            column=1,
        ).number_format = "mm/dd/yyyy"

    ws.freeze_panes = "A4"

    widths = {
        "A": 12,
        "B": 12,
        "C": 24,
        "D": 18,
        "E": 9,
        "F": 9,
        "G": 12,
        "H": 12,
        "I": 16,
        "J": 11,
        "K": 11,
        "L": 12,
        "M": 10,
        "N": 32,
    }

    for column, width in widths.items():
        ws.column_dimensions[column].width = width

    return ws


# ==================================================
# RUNNING / ATHLETICISM SHEET
# ==================================================

def create_running_sheet(
    workbook,
    week_number,
):
    """
    Track running, sprinting, agility,
    plyometrics, and other athletic work.
    """

    ws = workbook.create_sheet(
        "Running & Athleticism"
    )

    style_title(
        ws,
        "A1:L1",
        f"Week {week_number} - Running & Athleticism",
    )

    headers = [
        "Date",
        "Day",
        "Session Type",
        "Planned Work",
        "Target",
        "Actual Distance",
        "Actual Time",
        "Actual Pace",
        "RPE",
        "Pain",
        "Quality",
        "Notes",
    ]

    ws.append([])
    ws.append(headers)

    style_header_row(
        ws,
        row_number=3,
        start_column=1,
        end_column=12,
    )

    for _ in range(14):
        ws.append(
            [""] * 12
        )

    quality_dropdown = DataValidation(
        type="list",
        formula1='"Excellent,Good,Average,Poor"',
        allow_blank=True,
    )

    ws.add_data_validation(
        quality_dropdown
    )

    quality_dropdown.add(
        "K4:K17"
    )

    ws.freeze_panes = "A4"

    widths = {
        "A": 12,
        "B": 12,
        "C": 20,
        "D": 32,
        "E": 20,
        "F": 15,
        "G": 14,
        "H": 14,
        "I": 10,
        "J": 10,
        "K": 14,
        "L": 32,
    }

    for column, width in widths.items():
        ws.column_dimensions[column].width = width

    return ws


# ==================================================
# NUTRITION / RECOVERY SHEET
# ==================================================

def create_recovery_sheet(
    workbook,
    week_number,
    week_dates,
):
    """
    Create one lightweight row per day.

    This gives the coach recovery and nutrition data
    without requiring a huge amount of daily logging.
    """

    ws = workbook.create_sheet(
        "Nutrition & Recovery"
    )

    style_title(
        ws,
        "A1:M1",
        f"Week {week_number} - Nutrition & Recovery",
    )

    headers = [
        "Date",
        "Day",
        "Body Weight",
        "Calories",
        "Protein",
        "Carbs",
        "Fat",
        "Sleep Hours",
        "Energy",
        "Soreness",
        "Pain",
        "Hydration",
        "Notes",
    ]

    ws.append([])
    ws.append(headers)

    style_header_row(
        ws,
        row_number=3,
        start_column=1,
        end_column=13,
    )

    for week_date in week_dates:

        ws.append([
            week_date,
            week_date.strftime("%A"),
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ])

    for row in range(4, 11):
        ws.cell(
            row=row,
            column=1,
        ).number_format = "mm/dd/yyyy"

    hydration_dropdown = DataValidation(
        type="list",
        formula1='"Low,Okay,Good,Excellent"',
        allow_blank=True,
    )

    ws.add_data_validation(
        hydration_dropdown
    )

    hydration_dropdown.add(
        "L4:L10"
    )

    ws.freeze_panes = "A4"

    widths = {
        "A": 12,
        "B": 12,
        "C": 14,
        "D": 12,
        "E": 12,
        "F": 12,
        "G": 12,
        "H": 13,
        "I": 11,
        "J": 11,
        "K": 11,
        "L": 14,
        "M": 32,
    }

    for column, width in widths.items():
        ws.column_dimensions[column].width = width

    return ws


# ==================================================
# WEEKLY CHECK-IN SHEET
# ==================================================

def create_checkin_sheet(
    workbook,
    week_number,
):
    """
    Create the short end-of-week review.

    Step 11 will eventually let the AI use this
    information when designing the next week.
    """

    ws = workbook.create_sheet(
        "Weekly Check-In"
    )

    style_title(
        ws,
        "A1:F1",
        f"Week {week_number} - Weekly Check-In",
    )

    ws["A3"] = "Metric"
    ws["B3"] = "Response"

    checkin_fields = [
        "Biggest Win",
        "Biggest Challenge",
        "Strength Progress",
        "Running / Athletic Progress",
        "Average Energy",
        "Average Soreness",
        "Body Weight Change",
        "Pain / Injury Notes",
    ]

    current_row = 4

    for field in checkin_fields:
        ws.cell(
            row=current_row,
            column=1,
            value=field,
        )

        current_row += 1

    style_header_row(
        ws,
        row_number=3,
        start_column=1,
        end_column=2,
    )

    ws["A13"] = "Next Week"
    ws["B13"] = "Decision"

    ws["A14"] = "What should increase?"
    ws["A15"] = "What should stay the same?"
    ws["A16"] = "What needs to decrease/change?"

    style_header_row(
        ws,
        row_number=13,
        start_column=1,
        end_column=2,
    )

    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 55

    for row in range(1, 17):

        ws.cell(
            row=row,
            column=1,
        ).alignment = Alignment(
            vertical="top",
            wrap_text=True,
        )

        ws.cell(
            row=row,
            column=2,
        ).alignment = Alignment(
            vertical="top",
            wrap_text=True,
        )

    return ws


# ==================================================
# MAIN WORKBOOK BUILDER
# ==================================================

def get_sample_week_plan(week_dates):
    """
    Return a structured example training week.

    This is temporary test data.

    Later, coach.py will generate or assemble this
    structure using the athlete's blueprint, database
    history, recovery, and progression recommendations.
    """

    return {
        "overview": [
            {
                "date": week_dates[0],
                "focus": "Lower Body Strength",
                "goal": "Build squat strength",
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
                "goal": "Prepare for next week",
            },
        ],

        "strength": [
            {
                "date": week_dates[0],
                "exercise": "Back Squat",
                "weight": 240,
                "sets": 3,
                "reps": 5,
                "rest": "2-3 min",
                "target_rpe": 8,
            },
            {
                "date": week_dates[0],
                "exercise": "Romanian Deadlift",
                "weight": 165,
                "sets": 3,
                "reps": 8,
                "rest": "90 sec",
                "target_rpe": 7,
            },
            {
                "date": week_dates[1],
                "exercise": "Bench Press",
                "weight": 160,
                "sets": 3,
                "reps": 5,
                "rest": "2-3 min",
                "target_rpe": 8,
            },
            {
                "date": week_dates[1],
                "exercise": "Pull-Ups",
                "weight": "BW",
                "sets": 4,
                "reps": 4,
                "rest": "2 min",
                "target_rpe": 8,
            },
        ],

        "running": [
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
        ],
    }

def populate_weekly_plan(
    workbook,
    week_plan,
):
    """
    Write structured weekly plan data into
    the workbook worksheets.
    """

    # ==================================================
    # WEEKLY OVERVIEW
    # ==================================================

    overview = workbook["Weekly Overview"]

    overview_row = 4

    for item in week_plan["overview"]:

        week_date = item["date"]

        overview.cell(
            row=overview_row,
            column=1,
            value=week_date.strftime("%A"),
        )

        overview.cell(
            row=overview_row,
            column=2,
            value=week_date,
        )

        overview.cell(
            row=overview_row,
            column=3,
            value=item["focus"],
        )

        overview.cell(
            row=overview_row,
            column=4,
            value=item["goal"],
        )

        overview_row += 1

    # ==================================================
    # STRENGTH TRAINING
    # ==================================================

    strength = workbook["Strength Training"]

    strength_row = 4

    for item in week_plan["strength"]:

        week_date = item["date"]

        strength.cell(
            row=strength_row,
            column=1,
            value=week_date,
        )

        strength.cell(
            row=strength_row,
            column=2,
            value=week_date.strftime("%A"),
        )

        strength.cell(
            row=strength_row,
            column=3,
            value=item["exercise"],
        )

        strength.cell(
            row=strength_row,
            column=4,
            value=item["weight"],
        )

        strength.cell(
            row=strength_row,
            column=5,
            value=item["sets"],
        )

        strength.cell(
            row=strength_row,
            column=6,
            value=item["reps"],
        )

        strength.cell(
            row=strength_row,
            column=7,
            value=item["rest"],
        )

        strength.cell(
            row=strength_row,
            column=8,
            value=item["target_rpe"],
        )

        strength_row += 1

    # ==================================================
    # RUNNING / ATHLETICISM
    # ==================================================

    running = workbook["Running & Athleticism"]

    running_row = 4

    for item in week_plan["running"]:

        week_date = item["date"]

        running.cell(
            row=running_row,
            column=1,
            value=week_date,
        )

        running.cell(
            row=running_row,
            column=2,
            value=week_date.strftime("%A"),
        )

        running.cell(
            row=running_row,
            column=3,
            value=item["session_type"],
        )

        running.cell(
            row=running_row,
            column=4,
            value=item["planned_work"],
        )

        running.cell(
            row=running_row,
            column=5,
            value=item["target"],
        )

        running_row += 1

def build_weekly_workbook(
    week_number=1,
    start_date=None,
    week_plan=None,
):
    """
    Build one complete weekly workbook.

    Other Python code will eventually call this
    function when the user asks the coach to
    generate a new training week.
    """

    week_dates = get_week_dates(
        start_date
    )

    # Create a new Excel workbook in memory.
    workbook = Workbook()

    # Build each worksheet.
    create_overview_sheet(
        workbook,
        week_number,
        week_dates,
    )

    create_strength_sheet(
        workbook,
        week_number,
    )

    create_running_sheet(
        workbook,
        week_number,
    )

    create_recovery_sheet(
        workbook,
        week_number,
        week_dates,
    )
    if week_plan is None:
        week_plan = build_weekly_plan(
            week_dates
        )

    populate_weekly_plan(
        workbook,
        week_plan,
    )

    create_checkin_sheet(
        workbook,
        week_number,
    )

    # Make sure the workouts directory exists.
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Build a unique filename containing
    # the week number and Monday-Sunday dates.
    filename = (
        f"week_{week_number}_"
        f"{week_dates[0].isoformat()}_"
        f"to_{week_dates[-1].isoformat()}.xlsx"
    )

    output_path = (
        OUTPUT_DIR / filename
    )

    # Actually write the workbook to disk.
    workbook.save(
        output_path
    )

    return output_path


# ==================================================
# DIRECT TEST
# ==================================================

if __name__ == "__main__":

    path = build_weekly_workbook(
        week_number=1
    )

    print(
        f"Workbook created: {path}"
    )