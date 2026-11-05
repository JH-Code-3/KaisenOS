export interface DailyNutritionTotals {
  date: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
}

export interface LatestBodyWeight {
  date: string;
  body_weight: number;
}

export interface LatestRecovery {
  recovery_date: string;
  sleep_hours: number | null;
  energy: number | null;
  soreness: number | null;
  pain: number | null;
}

export interface WorkoutSet {
  id: number;
  session_id: number;
  exercise_name: string;
  set_number: number;
  reps: number | null;
  weight: number | null;
  rpe: number | null;
  rest_seconds: number | null;
  pain: number | null;
  duration_seconds: number | null;
  is_completed: number;
  notes: string | null;
}

export interface WorkoutSession {
  id: number;
  session_date: string;
  session_time: string | null;
  name: string | null;
  notes: string | null;
  created_at: string;
  sets: WorkoutSet[];
  analysis?: {
    session_id: number;
    session_date: string;
    exercises: {
      exercise: string;
      total_volume: number;
      best_e1rm: number | null;
      sets: number;
    }[];
  };
}

export interface WeeklyTrainingVolume {
  window_start: string;
  window_end: string;
  session_count: number;
  total_volume: number;
}

export interface Overview {
  date: string;
  todays_nutrition: DailyNutritionTotals;
  latest_body_weight: LatestBodyWeight | null;
  latest_recovery: LatestRecovery | null;
  recent_workout_session: WorkoutSession | null;
  weekly_training_volume: WeeklyTrainingVolume;
}

export interface AppSettings {
  ollama_model: string;
}

// ---------- Workouts page ----------

export interface SetIn {
  exercise_name: string;
  set_number: number;
  reps: number | null;
  weight: number | null;
  rpe: number | null;
  pain: number | null;
  is_completed: boolean;
}

export interface WorkoutSessionIn {
  session_date: string;
  name: string | null;
  notes: string | null;
  sets: SetIn[];
}

/** Most recent entry for an exercise (old or per-set log). */
export interface ExerciseLast {
  date: string;
  exercise: string;
  weight: number | null;
  sets: number | null;
  reps: number | null;
  rpe: number | null;
  pain: number | null;
  e1rm: number | null;
  volume: number | null;
}

export interface ProgressionRecommendation {
  exercise: string;
  decision: "INCREASE" | "HOLD" | "REDUCE" | "NO DATA";
  current_weight?: number | null;
  reason: string;
}

// ---------- Nutrition page ----------

export interface MealItem {
  id: number;
  meal_id: number;
  food_id: number | null;
  food_name: string;
  quantity: number;
  serving_unit: string | null;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  fiber_g: number | null;
  is_estimate: number;
}

export interface Meal {
  id: number;
  meal_date: string;
  meal_type: string | null;
  notes: string | null;
  items: MealItem[];
}

export interface MealItemIn {
  food_name: string;
  quantity: number;
  serving_unit: string | null;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  food_id: number | null;
  is_estimate: boolean;
  save_as_food: boolean;
}

export interface MealIn {
  meal_date: string;
  meal_type: string | null;
  notes: string | null;
  items: MealItemIn[];
}

/** A saved food. Macro values are per one serving_unit. */
export interface Food {
  id: number;
  name: string;
  serving_size: number | null;
  serving_unit: string | null;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  is_estimate: number;
}

export interface NutritionTarget {
  id: number;
  effective_date: string;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
}

/** Row the CLI coach wrote to the original daily-totals table. */
export interface LegacyNutritionEntry {
  id: number;
  nutrition_date: string;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  notes: string | null;
}

export interface NutritionDay {
  date: string;
  meals: Meal[];
  legacy_entries: LegacyNutritionEntry[];
  totals: DailyNutritionTotals;
  target: NutritionTarget | null;
}

export interface WeeklyNutrition {
  start_date: string;
  end_date: string;
  days_logged: number;
  avg_calories: number;
  avg_protein_g: number;
  avg_carbs_g: number;
  avg_fat_g: number;
  days: DailyNutritionTotals[];
}

// ---------- Recovery / Body pages ----------

export interface RecoveryEntry {
  id: number;
  recovery_date: string;
  sleep_hours: number | null;
  energy: number | null;
  soreness: number | null;
  pain: number | null;
  notes: string | null;
}

export interface RecoveryFlag {
  metric: "pain" | "sleep_hours" | "energy" | "soreness";
  value: number;
  severity: "hold" | "reduce";
  message: string;
}

export interface RecoveryStatus {
  status: "ok" | "hold" | "reduce" | "no_data" | "stale";
  latest: RecoveryEntry | null;
  flags: RecoveryFlag[];
  days_old: number | null;
}

export interface BodyEntry {
  id: number;
  metric_date: string;
  body_weight: number | null;
  body_fat: number | null;
  waist: number | null;
  notes: string | null;
}

export interface BodyWeightSummary {
  latest_date: string;
  latest_weight: number;
  avg_7d: number | null;
  entries_7d: number;
  prev_avg_7d: number | null;
  prev_entries_7d: number;
  weekly_change: number | null;
}

// ---------- AI Coach ----------

export type Readiness = "GO" | "HOLD" | "REDUCE" | "UNKNOWN";

export interface CoachFlag {
  metric: string;
  severity: "hold" | "reduce";
  message: string;
  source: "check-in" | "Garmin";
}

export interface LoadWeek {
  start: string;
  end: string;
  lifting_volume_lb: number;
  lifting_days: number;
  running_miles: number;
  runs: number;
}

export interface LoadFlag {
  metric: "lifting_volume_lb" | "running_miles";
  severity: "info" | "caution" | "high";
  change_pct?: number;
  message: string;
}

export interface PlannedExercise {
  exercise: string;
  decision: "INCREASE" | "HOLD" | "REDUCE" | "NO_HISTORY" | "NO DATA";
  previous_weight: number | null;
  recommended_weight: number | null;
  reason: string;
}

export interface CoachInsights {
  today: string;
  readiness: Readiness;
  recovery: {
    flags: CoachFlag[];
    notes: string[];
    checkin: RecoveryEntry | null;
    garmin_last_night: Record<string, number | string | null> | null;
    garmin_available: boolean;
  };
  load_by_week: LoadWeek[];
  load_flags: LoadFlag[];
  next_workout: {
    session_name: string;
    last_done: string;
    readiness: Readiness;
    exercises: PlannedExercise[];
  } | null;
  pain_reports: { date: string; where: string; pain: number }[];
  safety_notes: string[];
  intensity: TrainingIntensity;
  phase: PhaseOverview;
}

export interface GarminSyncStatus {
  started_at: string;
  finished_at: string | null;
  range_start: string;
  range_end: string;
  status: "running" | "ok" | "partial" | "failed";
  error: string | null;
  raw_responses: number;
  mapped_days: number;
  fields_mapped: boolean;
}

export interface CoachStatus {
  model: string;
  model_ready: boolean;
  local_models: string[];
  ollama_url: string;
  ollama_error: string | null;
  garmin: GarminSyncStatus | null;
  garmin_schedule_on: boolean;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// ---------- Note import ----------

export interface ImportItem {
  food_name: string;
  quantity: number | null;
  serving_unit: string | null;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  is_estimate: boolean;
  macro_source: "notes" | "my_foods" | "estimate" | "none";
  source: string;
}

export interface ImportMeal {
  meal_type: string | null;
  items: ImportItem[];
}

export interface ImportExercise {
  exercise: string;
  weight: number | null;
  reps: number | null;
  sets: number;
  rpe: number | null;
  source: string;
}

export interface ImportActivity {
  session_type: "running" | "basketball" | "conditioning" | "sprint" | "plyometric" | "agility";
  subtype: BasketballType | null;
  run_type: RunType | null;
  distance_miles: number | null;
  duration_minutes: number | null;
  rpe: number | null;
  source: string;
}

export interface ImportDay {
  date: string | null;
  include: boolean;
  meals: ImportMeal[];
  workouts: { name: string | null; exercises: ImportExercise[] }[];
  activities: ImportActivity[];
  body_weight: number | null;
  recovery: { sleep_hours: number | null; energy: number | null; soreness: number | null; pain: number | null } | null;
  notes: string | null;
  warnings: string[];
  not_imported: string[];
  original_text: string;
  existing: { meals?: number; workouts?: number; recovery?: number; body?: number; activities?: number };
  include_meals: boolean;
  include_workouts: boolean;
  include_recovery: boolean;
  include_body: boolean;
  include_activities: boolean;
}

export interface ImportJob {
  status: "running" | "done" | "failed";
  done: number;
  total: number;
  days: ImportDay[] | null;
  error: string | null;
}

export interface ImportBatch {
  id: number;
  created_at: string;
  days: number;
  meals: number;
  workout_sessions: number;
  recovery_entries: number;
  body_entries: number;
  undone_at: string | null;
}

// ---------- Goals & phase ----------

export type PhaseKey = "cut" | "bulk" | "maintain" | "recomp";

export interface AthleteProfile {
  sex: "male" | "female" | null;
  birth_year: number | null;
  height_in: number | null;
  experience: "beginner" | "intermediate" | "advanced" | null;
  sports: Sport[] | null;
  effective_sports: Sport[];
}

export type Sport = "lifting" | "running" | "basketball" | "other";

export interface EnergyBalance {
  window_days: number;
  days_logged: number;
  avg_intake: number | null;
  avg_protein_g: number | null;
  weigh_ins: number;
  latest_weight: number | null;
  weekly_change_lb: number | null;
  weekly_change_pct: number | null;
  maintenance_kcal: number | null;
  maintenance_method: string | null;
  confidence: "high" | "medium" | "low" | "none";
  notes: string[];
}

export interface CoachPlan {
  id: number;
  created_at: string;
  phase: PhaseKey;
  start_date: string;
  start_weight: number | null;
  target_weight: number | null;
  target_date: string | null;
  weekly_rate_pct: number;
  calorie_target: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  training_days_per_week: number | null;
  priorities: string | null;
  notes: string | null;
}

export interface PhaseOverview {
  profile: AthleteProfile;
  energy_balance: EnergyBalance;
  latest_body_fat: number | null;
  active_plan: CoachPlan | null;
  progress: { weeks_in: number; checks: { status: "good" | "warn" | "unknown"; message: string }[] } | null;
  hints: string[];
  phases: Record<PhaseKey, { label: string; rate_range: [number, number]; default_rate: number }>;
}

export interface PlanPreview {
  phase: PhaseKey;
  weekly_rate_pct: number;
  weekly_change_lb: number;
  calorie_target: number;
  daily_energy_delta: number;
  protein_g: number;
  fat_g: number;
  carbs_g: number;
  weeks_to_target: number | null;
  warnings: string[];
  start_weight: number;
  maintenance_kcal: number;
}

export interface IntensityLift {
  exercise: string;
  sessions: number;
  sets_per_week: number;
  avg_rpe: number | null;
  hard_set_share_pct: number | null;
  rpe_logged_pct: number;
  best_e1rm: number | null;
  e1rm_trend: "improving" | "declining" | "stable" | null;
  e1rm_change_lb: number | null;
  last_top_set: string | null;
  last_top_set_pct_of_best: number | null;
}

export interface TrainingIntensity {
  window_days: number;
  lifts: IntensityLift[];
  muscle_groups: { muscle: string; working_sets_per_week: number; status: "low" | "in range" | "high" }[];
  sets_range_per_week: [number, number];
}

// ---------- Running & athleticism ----------

export type SessionType = "running" | "sprint" | "plyometric" | "agility" | "conditioning" | "basketball";
export type BasketballType = "practice" | "game" | "skills" | "pickup";
export type DayStatus = "open" | "busy" | "practice" | "game";
export type RunType = "easy" | "recovery" | "long" | "tempo" | "intervals" | "race";

export interface AthleticSession {
  id: number;
  session_date: string;
  session_type: SessionType;
  subtype: BasketballType | null;
  run_type: RunType | null;
  distance_miles: number | null;
  duration_minutes: number | null;
  pace_per_mile: number | null;
  sprint_distance_yards: number | null;
  sprint_time_seconds: number | null;
  jump_height_inches: number | null;
  reps: number | null;
  rpe: number | null;
  notes: string | null;
  source: "log" | "legacy";
  garmin_activity_id?: number | null;
}

export interface RunningSummary {
  today: string;
  weekly_mileage: { week_start: string; miles: number; runs: number; long_run: number }[];
  intensity_split: {
    window_days: number;
    miles: { easy: number; moderate: number; hard: number; unknown: number };
    easy_share_pct: number | null;
    target_easy_pct: number;
    status: "ok" | "too_hard" | null;
  };
  bests: {
    fastest_pace: { pace: number; pace_label: string; distance_miles: number; date: string } | null;
    longest_run: { distance_miles: number; date: string } | null;
    sprints: { distance_yards: number; time_seconds: number; date: string }[];
    best_jump: { inches: number; date: string } | null;
  };
  five_k_estimate: { minutes: number; label: string; based_on: { date: string; distance_miles: number; duration: string } } | null;
  pace_points: { date: string; pace: number; distance_miles: number; effort: string }[];
  sessions_last_28d: Record<SessionType, number>;
  avg_easy_pace_28d: string | null;
  load: {
    weekly: { week_start: string; basketball: number; other: number; basketball_sessions: number; basketball_minutes: number }[];
    acute_7d: number;
    chronic_weekly_avg: number;
    acwr: number | null;
    status: "ok" | "spike" | "low" | null;
    unrated_sessions_28d: number;
  };
}

// ---------- Weekly planner ----------

export interface PlanItem {
  id: number;
  item_date: string;
  category: "strength" | "running" | "basketball";
  exercise: string | null;
  prescribed_weight: number | null;
  sets: number | null;
  reps: number | null;
  rest: string | null;
  target_rpe: number | null;
  session_type: string | null;
  planned_work: string | null;
  target: string | null;
  notes: string | null;
  is_completed: number;
  auto_completed: boolean;
  done: boolean;
}

export interface PlanWeek {
  id: number;
  week_start: string;
  created_at: string;
  days: { date: string; focus: string; status: DayStatus; items: PlanItem[] }[];
  notes: string[];
  done: number;
  total: number;
}

// ---------- Garmin (read-only) ----------

export interface GarminNight {
  date: string;
  sleep_seconds: number | null;
  sleep_score: number | null;
  hrv_overnight_avg: number | null;
  hrv_status: string | null;
  resting_hr: number | null;
  body_battery_high: number | null;
  body_battery_low: number | null;
  stress_avg: number | null;
}

export interface GarminActivity {
  activity_id: number;
  date: string;
  type: string;
  label: string;
  maps_to: "basketball" | "running" | "conditioning";
  minutes: number | null;
  miles: number | null;
  avg_hr: number | null;
  max_hr: number | null;
  training_load: number | null;
  aerobic_effect: number | null;
  possible_duplicate: boolean;
}
