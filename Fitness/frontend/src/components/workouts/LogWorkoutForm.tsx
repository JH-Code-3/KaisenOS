import { useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { SetIn, WorkoutSession, WorkoutSessionIn } from "../../lib/types";
import { todayLocal, formatShortDate } from "../../lib/dates";
import { ExerciseHint } from "./ExerciseHint";
import { inputClass, inputStyle, cardStyle, parseNumber } from "../../lib/ui";

// Form values are kept as strings so half-typed numbers ("7.") survive
// re-renders; they're parsed and validated only on Review.
interface DraftSet {
  key: number;
  weight: string;
  reps: string;
  rpe: string;
  pain: string;
}

interface DraftExercise {
  key: number;
  name: string;
  /** Name last committed (on blur) — drives the history hint. */
  lookupName: string;
  sets: DraftSet[];
}

let nextKey = 1;
const newSet = (from?: DraftSet): DraftSet => ({
  key: nextKey++,
  weight: from?.weight ?? "",
  reps: from?.reps ?? "",
  rpe: from?.rpe ?? "",
  pain: "",
});
const newExercise = (): DraftExercise => ({ key: nextKey++, name: "", lookupName: "", sets: [newSet()] });

const SET_GRID = "grid grid-cols-[2rem_1fr_1fr_1fr_1fr_2rem] items-center gap-2";

/** Turn the draft into the API payload, or a list of problems to fix. */
function buildPayload(
  date: string,
  name: string,
  notes: string,
  exercises: DraftExercise[],
): { payload: WorkoutSessionIn; errors: string[] } {
  const errors: string[] = [];
  const sets: SetIn[] = [];
  // Set numbers continue if the same exercise appears in two blocks.
  const setCounts = new Map<string, number>();

  if (!date) errors.push("Pick a date.");

  exercises.forEach((exercise, index) => {
    const exerciseName = exercise.name.trim();
    const label = exerciseName || `Exercise ${index + 1}`;
    const filled = exercise.sets.filter((s) => s.weight || s.reps || s.rpe || s.pain);

    if (!exerciseName && filled.length === 0) return; // untouched row
    if (!exerciseName) errors.push(`${label}: add an exercise name.`);
    if (filled.length === 0) errors.push(`${label}: log at least one set.`);

    filled.forEach((s, i) => {
      const setLabel = `${label}, set ${i + 1}`;
      const weight = parseNumber(s.weight);
      const reps = parseNumber(s.reps);
      const rpe = parseNumber(s.rpe);
      const pain = parseNumber(s.pain);

      if (reps == null) errors.push(`${setLabel}: reps are required.`);
      else if (!Number.isInteger(reps) || reps < 0) errors.push(`${setLabel}: reps must be a whole number.`);
      if (weight != null && (Number.isNaN(weight) || weight < 0)) errors.push(`${setLabel}: weight can't be negative.`);
      if (rpe != null && (Number.isNaN(rpe) || rpe < 0 || rpe > 10)) errors.push(`${setLabel}: RPE must be 0–10.`);
      if (pain != null && (Number.isNaN(pain) || pain < 0 || pain > 10)) errors.push(`${setLabel}: pain must be 0–10.`);

      const setNumber = (setCounts.get(exerciseName) ?? 0) + 1;
      setCounts.set(exerciseName, setNumber);

      sets.push({
        exercise_name: exerciseName,
        set_number: setNumber,
        weight,
        reps,
        rpe,
        pain,
        is_completed: true,
      });
    });
  });

  if (errors.length === 0 && sets.length === 0) errors.push("Add at least one exercise with a set.");

  return {
    payload: { session_date: date, name: name.trim() || null, notes: notes.trim() || null, sets },
    errors,
  };
}

interface Props {
  exerciseNames: string[];
  onSaved: (session: WorkoutSession) => void;
  onCancel: () => void;
}

export function LogWorkoutForm({ exerciseNames, onSaved, onCancel }: Props) {
  const [date, setDate] = useState(todayLocal());
  const [name, setName] = useState("");
  const [notes, setNotes] = useState("");
  const [exercises, setExercises] = useState<DraftExercise[]>([newExercise()]);
  const [errors, setErrors] = useState<string[]>([]);
  const [review, setReview] = useState<WorkoutSessionIn | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  function updateExercise(key: number, patch: Partial<DraftExercise>) {
    setExercises((list) => list.map((e) => (e.key === key ? { ...e, ...patch } : e)));
  }

  function updateSet(exerciseKey: number, setKey: number, patch: Partial<DraftSet>) {
    setExercises((list) =>
      list.map((e) =>
        e.key === exerciseKey ? { ...e, sets: e.sets.map((s) => (s.key === setKey ? { ...s, ...patch } : s)) } : e,
      ),
    );
  }

  function addSet(exerciseKey: number) {
    setExercises((list) =>
      list.map((e) => (e.key === exerciseKey ? { ...e, sets: [...e.sets, newSet(e.sets[e.sets.length - 1])] } : e)),
    );
  }

  function removeSet(exerciseKey: number, setKey: number) {
    setExercises((list) =>
      list.map((e) => (e.key === exerciseKey ? { ...e, sets: e.sets.filter((s) => s.key !== setKey) } : e)),
    );
  }

  function goToReview() {
    const result = buildPayload(date, name, notes, exercises);
    setErrors(result.errors);
    if (result.errors.length === 0) {
      setSaveError(null);
      setReview(result.payload);
    }
  }

  async function save() {
    if (!review) return;
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await api.post<WorkoutSession>("/api/workouts/sessions", review);
      onSaved(saved);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  // ---------- Review step: nothing is written until "Save" ----------
  if (review) {
    const byExercise = new Map<string, SetIn[]>();
    review.sets.forEach((s) => byExercise.set(s.exercise_name, [...(byExercise.get(s.exercise_name) ?? []), s]));

    return (
      <section className="flex flex-col gap-4 rounded-lg border p-4" style={cardStyle}>
        <div>
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Review before saving
          </h2>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {formatShortDate(review.session_date)}
            {review.name ? ` · ${review.name}` : ""} · {review.sets.length} set{review.sets.length === 1 ? "" : "s"}
          </p>
        </div>

        {[...byExercise.entries()].map(([exerciseName, sets]) => (
          <div key={exerciseName}>
            <p className="mb-1 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              {exerciseName}
            </p>
            <table className="w-full max-w-md text-sm" style={{ color: "var(--text-secondary)" }}>
              <thead>
                <tr className="text-left text-xs" style={{ color: "var(--text-muted)" }}>
                  <th className="py-1 font-medium">Set</th>
                  <th className="py-1 font-medium">Weight</th>
                  <th className="py-1 font-medium">Reps</th>
                  <th className="py-1 font-medium">RPE</th>
                  <th className="py-1 font-medium">Pain</th>
                </tr>
              </thead>
              <tbody>
                {sets.map((s) => (
                  <tr key={s.set_number} className="border-t" style={{ borderColor: "var(--border-hairline)" }}>
                    <td className="py-1">{s.set_number}</td>
                    <td className="py-1">{s.weight != null ? `${s.weight} lb` : "BW"}</td>
                    <td className="py-1">{s.reps}</td>
                    <td className="py-1">{s.rpe ?? "—"}</td>
                    <td className="py-1">{s.pain ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

        {review.notes && (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Notes: {review.notes}
          </p>
        )}

        {saveError && (
          <p className="text-sm" style={{ color: "var(--status-critical)" }}>
            Couldn&rsquo;t save: {saveError}
          </p>
        )}

        <div className="flex gap-2">
          <button
            onClick={save}
            disabled={saving}
            className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
            style={{ background: "var(--series-1)", color: "#fff" }}
          >
            {saving ? "Saving…" : "Save workout"}
          </button>
          <button
            onClick={() => setReview(null)}
            disabled={saving}
            className="rounded-md px-3 py-1.5 text-sm"
            style={{ background: "var(--surface-2)", color: "var(--text-primary)" }}
          >
            Back to edit
          </button>
        </div>
      </section>
    );
  }

  // ---------- Entry step ----------
  return (
    <section className="flex flex-col gap-4 rounded-lg border p-4" style={cardStyle}>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Log a workout
        </h2>
        <button onClick={onCancel} aria-label="Close" style={{ color: "var(--text-muted)" }}>
          <X size={16} />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[10rem_1fr]">
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} style={inputStyle} />
        </label>
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
          Session name (optional)
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Upper A, Leg day"
            className={inputClass}
            style={inputStyle}
          />
        </label>
      </div>

      <datalist id="exercise-names">
        {exerciseNames.map((n) => (
          <option key={n} value={n} />
        ))}
      </datalist>

      {exercises.map((exercise, index) => (
        <div
          key={exercise.key}
          className="flex flex-col gap-2 rounded-md border p-3"
          style={{ borderColor: "var(--border-hairline)" }}
        >
          <div className="flex items-start gap-2">
            <div className="flex flex-1 flex-col gap-1">
              <input
                list="exercise-names"
                value={exercise.name}
                onChange={(e) => updateExercise(exercise.key, { name: e.target.value })}
                onBlur={() => updateExercise(exercise.key, { lookupName: exercise.name.trim() })}
                placeholder={`Exercise ${index + 1} (e.g. Bench Press)`}
                aria-label={`Exercise ${index + 1} name`}
                className={`${inputClass} font-medium`}
                style={inputStyle}
              />
              {exercise.lookupName && <ExerciseHint exerciseName={exercise.lookupName} />}
            </div>
            {exercises.length > 1 && (
              <button
                onClick={() => setExercises((list) => list.filter((e) => e.key !== exercise.key))}
                aria-label={`Remove ${exercise.name || `exercise ${index + 1}`}`}
                className="mt-2"
                style={{ color: "var(--text-muted)" }}
              >
                <Trash2 size={15} />
              </button>
            )}
          </div>

          <div className={`${SET_GRID} text-xs`} style={{ color: "var(--text-muted)" }}>
            <span>Set</span>
            <span>Weight (lb)</span>
            <span>Reps</span>
            <span>RPE</span>
            <span>Pain</span>
            <span />
          </div>

          {exercise.sets.map((s, setIndex) => (
            <div key={s.key} className={SET_GRID}>
              <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                {setIndex + 1}
              </span>
              {(
                [
                  ["weight", "decimal", "0.5", "BW"],
                  ["reps", "numeric", "1", ""],
                  ["rpe", "decimal", "0.5", "0–10"],
                  ["pain", "decimal", "1", "0–10"],
                ] as const
              ).map(([field, inputMode, step, placeholder]) => (
                <input
                  key={field}
                  type="number"
                  min={0}
                  max={field === "rpe" || field === "pain" ? 10 : undefined}
                  step={step}
                  inputMode={inputMode}
                  placeholder={placeholder}
                  value={s[field]}
                  onChange={(e) => updateSet(exercise.key, s.key, { [field]: e.target.value })}
                  aria-label={`${exercise.name || `Exercise ${index + 1}`} set ${setIndex + 1} ${field}`}
                  className={`${inputClass} w-full min-w-0`}
                  style={inputStyle}
                />
              ))}
              {exercise.sets.length > 1 ? (
                <button
                  onClick={() => removeSet(exercise.key, s.key)}
                  aria-label={`Remove set ${setIndex + 1}`}
                  style={{ color: "var(--text-muted)" }}
                >
                  <X size={14} />
                </button>
              ) : (
                <span />
              )}
            </div>
          ))}

          <button
            onClick={() => addSet(exercise.key)}
            className="flex items-center gap-1 self-start text-xs"
            style={{ color: "var(--series-1)" }}
          >
            <Plus size={13} /> Add set
          </button>
        </div>
      ))}

      <button
        onClick={() => setExercises((list) => [...list, newExercise()])}
        className="flex items-center gap-1 self-start rounded-md px-3 py-1.5 text-sm"
        style={{ background: "var(--surface-2)", color: "var(--text-primary)" }}
      >
        <Plus size={14} /> Add exercise
      </button>

      <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
        Notes (optional)
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          placeholder="How did it feel? Anything to remember next time?"
          className={inputClass}
          style={inputStyle}
        />
      </label>

      {errors.length > 0 && (
        <ul className="list-disc pl-5 text-sm" style={{ color: "var(--status-critical)" }}>
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}

      <div className="flex gap-2">
        <button
          onClick={goToReview}
          className="rounded-md px-3 py-1.5 text-sm font-medium"
          style={{ background: "var(--series-1)", color: "#fff" }}
        >
          Review
        </button>
        <button
          onClick={onCancel}
          className="rounded-md px-3 py-1.5 text-sm"
          style={{ background: "var(--surface-2)", color: "var(--text-primary)" }}
        >
          Cancel
        </button>
      </div>
    </section>
  );
}
