import type { ImportDay } from "./types";

/** Build the save payload, or list what needs fixing first. */
export function buildCommit(days: ImportDay[]) {
  const errors: string[] = [];
  const out = [];

  for (const d of days.filter((x) => x.include)) {
    const meals = d.include_meals
      ? d.meals
          .map((m) => ({ meal_type: m.meal_type, items: m.items.filter((it) => it.food_name.trim()) }))
          .filter((m) => m.items.length)
      : [];
    const workouts = d.include_workouts
      ? d.workouts
          .map((w) => ({ name: w.name, exercises: w.exercises.filter((e) => e.exercise.trim()) }))
          .filter((w) => w.exercises.length)
      : [];
    const activities = d.include_activities ? d.activities ?? [] : [];
    const body_weight = d.include_body ? d.body_weight : null;
    const recovery = d.include_recovery ? d.recovery : null;

    if (!meals.length && !workouts.length && !activities.length && body_weight == null && !recovery) continue;
    const label = d.date ?? "A day with no date";
    if (!d.date) errors.push(`${label}: set a date or untick the day.`);
    for (const w of workouts)
      for (const e of w.exercises)
        if (!e.reps || e.reps < 1) errors.push(`${label}, ${e.exercise}: reps are missing.`);

    for (const a of activities)
      if (a.session_type === "basketball" && !a.duration_minutes) errors.push(`${label}, basketball: add the minutes.`);

    out.push({
      date: d.date,
      meals,
      workouts,
      activities: activities.map(({ source, ...rest }) => ({ ...rest, notes: source || null })),
      body_weight,
      recovery,
      notes: d.notes,
    });
  }

  if (!out.length && !errors.length) errors.push("Nothing selected to save.");
  return { days: out, errors };
}
