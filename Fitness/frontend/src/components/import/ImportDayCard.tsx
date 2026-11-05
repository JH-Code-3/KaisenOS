import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, X } from "lucide-react";
import type { ImportActivity, ImportDay, ImportExercise, ImportItem } from "../../lib/types";
import { BASKETBALL_LABELS, RUN_TYPE_LABELS, SESSION_LABELS } from "../../lib/running";
import { formatShortDate } from "../../lib/dates";
import { cardStyle, inputClass, inputStyle } from "../../lib/ui";
import { EstimateTag } from "../nutrition/EstimateTag";

const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack", "pre-workout", "post-workout"];

const num = (raw: string): number | null => (raw.trim() === "" ? null : Number(raw));
const small = `${inputClass} w-full min-w-0 px-1.5 py-1 text-xs`;

function NumberCell({ value, onChange, label, step = "any" }: { value: number | null; onChange: (v: number | null) => void; label: string; step?: string }) {
  return (
    <input
      type="number"
      min={0}
      step={step}
      value={value ?? ""}
      onChange={(e) => onChange(num(e.target.value))}
      aria-label={label}
      className={small}
      style={inputStyle}
    />
  );
}

function SectionToggle({
  checked,
  onChange,
  label,
  existing,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  existing?: number;
}) {
  return (
    <label className="flex flex-wrap items-center gap-2 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
      {existing ? (
        <span className="normal-case tracking-normal" style={{ color: checked ? "var(--text-muted)" : "var(--status-warning)" }}>
          {checked
            ? `· adds to the ${existing} already logged for this date`
            : `· this date already has ${existing} logged ${existing === 1 ? "entry" : "entries"}, so it's off`}
        </span>
      ) : null}
    </label>
  );
}

const SOURCE_LABEL: Record<ImportItem["macro_source"], string> = {
  notes: "from notes",
  my_foods: "My foods",
  estimate: "estimated",
  none: "no values",
};

interface Props {
  day: ImportDay;
  index: number;
  onChange: (day: ImportDay) => void;
}

export function ImportDayCard({ day, index, onChange }: Props) {
  const [showOriginal, setShowOriginal] = useState(false);
  const set = (patch: Partial<ImportDay>) => onChange({ ...day, ...patch });

  const setItem = (mi: number, ii: number, patch: Partial<ImportItem>) =>
    set({
      meals: day.meals.map((m, i) =>
        i === mi ? { ...m, items: m.items.map((it, j) => (j === ii ? { ...it, ...patch } : it)) } : m,
      ),
    });
  const removeItem = (mi: number, ii: number) =>
    set({
      meals: day.meals
        .map((m, i) => (i === mi ? { ...m, items: m.items.filter((_, j) => j !== ii) } : m))
        .filter((m) => m.items.length),
    });
  const setExercise = (wi: number, ei: number, patch: Partial<ImportExercise>) =>
    set({
      workouts: day.workouts.map((w, i) =>
        i === wi ? { ...w, exercises: w.exercises.map((e, j) => (j === ei ? { ...e, ...patch } : e)) } : w,
      ),
    });
  const removeExercise = (wi: number, ei: number) =>
    set({
      workouts: day.workouts
        .map((w, i) => (i === wi ? { ...w, exercises: w.exercises.filter((_, j) => j !== ei) } : w))
        .filter((w) => w.exercises.length),
    });

  const setActivity = (ai: number, patch: Partial<ImportActivity>) =>
    set({ activities: day.activities.map((a, i) => (i === ai ? { ...a, ...patch } : a)) });
  const removeActivity = (ai: number) => set({ activities: day.activities.filter((_, i) => i !== ai) });

  const dayCalories = day.meals.flatMap((m) => m.items).reduce((s, it) => s + (it.calories ?? 0), 0);
  const dayProtein = day.meals.flatMap((m) => m.items).reduce((s, it) => s + (it.protein_g ?? 0), 0);

  return (
    <article className="flex flex-col gap-3 rounded-lg border p-4" style={{ ...cardStyle, opacity: day.include ? 1 : 0.55 }}>
      <header className="flex flex-wrap items-center gap-3">
        <input
          type="checkbox"
          checked={day.include}
          onChange={(e) => set({ include: e.target.checked })}
          aria-label={`Include day ${index + 1}`}
          className="h-4 w-4"
        />
        <input
          type="date"
          value={day.date ?? ""}
          onChange={(e) => set({ date: e.target.value || null })}
          aria-label={`Day ${index + 1} date`}
          className={`${inputClass} text-sm`}
          style={{ ...inputStyle, borderColor: day.date ? "var(--border-hairline)" : "var(--status-critical)" }}
        />
        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {day.date ? formatShortDate(day.date) : "No date — set one"}
        </span>
        {day.meals.length > 0 && (
          <span className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
            {Math.round(dayCalories).toLocaleString()} kcal · {Math.round(dayProtein)} g protein
          </span>
        )}
      </header>

      {day.warnings.map((w) => (
        <p key={w} className="flex items-center gap-1.5 text-xs" style={{ color: "var(--status-warning)" }}>
          <AlertTriangle size={13} /> {w}
        </p>
      ))}

      {day.include && (
        <>
          {day.meals.length > 0 && (
            <section className="flex flex-col gap-2">
              <SectionToggle
                checked={day.include_meals}
                onChange={(v) => set({ include_meals: v })}
                label="Meals"
                existing={day.existing?.meals}
              />
              {day.include_meals && (
                <div className="overflow-x-auto">
                  <div className="flex min-w-[42rem] flex-col gap-2">
                    {day.meals.map((meal, mi) => (
                      <div key={mi} className="flex flex-col gap-1">
                        <select
                          value={meal.meal_type ?? ""}
                          onChange={(e) =>
                            set({ meals: day.meals.map((m, i) => (i === mi ? { ...m, meal_type: e.target.value || null } : m)) })
                          }
                          aria-label="Meal type"
                          className={`${small} w-36`}
                          style={inputStyle}
                        >
                          <option value="">Meal</option>
                          {MEAL_TYPES.map((t) => (
                            <option key={t} value={t}>
                              {t[0].toUpperCase() + t.slice(1)}
                            </option>
                          ))}
                        </select>
                        <div className="grid grid-cols-[minmax(10rem,2fr)_4rem_4rem_repeat(4,4rem)_6rem_1.25rem] gap-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
                          <span>Food</span><span>Qty</span><span>Unit</span><span>kcal</span><span>Protein</span><span>Carbs</span><span>Fat</span><span>Values</span><span />
                        </div>
                        {meal.items.map((it, ii) => (
                          <div key={ii} className="grid grid-cols-[minmax(10rem,2fr)_4rem_4rem_repeat(4,4rem)_6rem_1.25rem] items-center gap-1.5" title={it.source ? `From: "${it.source}"` : undefined}>
                            <input value={it.food_name} onChange={(e) => setItem(mi, ii, { food_name: e.target.value })} aria-label="Food" className={small} style={inputStyle} />
                            <NumberCell value={it.quantity} onChange={(v) => setItem(mi, ii, { quantity: v })} label="Quantity" />
                            <input value={it.serving_unit ?? ""} onChange={(e) => setItem(mi, ii, { serving_unit: e.target.value || null })} aria-label="Unit" className={small} style={inputStyle} />
                            {(["calories", "protein_g", "carbs_g", "fat_g"] as const).map((k) => (
                              <NumberCell
                                key={k}
                                value={it[k]}
                                onChange={(v) => setItem(mi, ii, { [k]: v })}
                                label={k}
                              />
                            ))}
                            <span className="flex items-center text-[11px]" style={{ color: "var(--text-muted)" }}>
                              {it.is_estimate ? <EstimateTag /> : SOURCE_LABEL[it.macro_source]}
                            </span>
                            <button onClick={() => removeItem(mi, ii)} aria-label={`Remove ${it.food_name}`} style={{ color: "var(--text-muted)" }}>
                              <X size={13} />
                            </button>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          {day.workouts.length > 0 && (
            <section className="flex flex-col gap-2">
              <SectionToggle
                checked={day.include_workouts}
                onChange={(v) => set({ include_workouts: v })}
                label="Workout"
                existing={day.existing?.workouts}
              />
              {day.include_workouts &&
                day.workouts.map((w, wi) => (
                  <div key={wi} className="overflow-x-auto">
                    <div className="flex min-w-[34rem] flex-col gap-1.5">
                      <input
                        value={w.name ?? ""}
                        placeholder="Session name (optional)"
                        onChange={(e) =>
                          set({ workouts: day.workouts.map((x, i) => (i === wi ? { ...x, name: e.target.value || null } : x)) })
                        }
                        aria-label="Session name"
                        className={`${small} w-56`}
                        style={inputStyle}
                      />
                      <div className="grid grid-cols-[minmax(10rem,2fr)_4.5rem_4rem_4rem_4rem_1.25rem] gap-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
                        <span>Exercise</span><span>Weight lb</span><span>Reps</span><span>Sets</span><span>RPE</span><span />
                      </div>
                      {w.exercises.map((ex, ei) => (
                        <div key={ei} className="grid grid-cols-[minmax(10rem,2fr)_4.5rem_4rem_4rem_4rem_1.25rem] items-center gap-1.5" title={ex.source ? `From: "${ex.source}"` : undefined}>
                          <input value={ex.exercise} onChange={(e) => setExercise(wi, ei, { exercise: e.target.value })} aria-label="Exercise" className={small} style={inputStyle} />
                          <NumberCell value={ex.weight} onChange={(v) => setExercise(wi, ei, { weight: v })} label="Weight" />
                          <NumberCell value={ex.reps} onChange={(v) => setExercise(wi, ei, { reps: v })} label="Reps" step="1" />
                          <NumberCell value={ex.sets} onChange={(v) => setExercise(wi, ei, { sets: v ?? 1 })} label="Sets" step="1" />
                          <NumberCell value={ex.rpe} onChange={(v) => setExercise(wi, ei, { rpe: v })} label="RPE" step="0.5" />
                          <button onClick={() => removeExercise(wi, ei)} aria-label={`Remove ${ex.exercise}`} style={{ color: "var(--text-muted)" }}>
                            <X size={13} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
            </section>
          )}

          {day.activities?.length > 0 && (
            <section className="flex flex-col gap-2">
              <SectionToggle
                checked={day.include_activities}
                onChange={(v) => set({ include_activities: v })}
                label="Basketball, runs & conditioning"
                existing={day.existing?.activities}
              />
              {day.include_activities && (
                <div className="overflow-x-auto">
                  <div className="flex min-w-[36rem] flex-col gap-1.5">
                    <div className="grid grid-cols-[7rem_8rem_4.5rem_4.5rem_4rem_1.25rem] gap-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
                      <span>Type</span><span>Kind</span><span>Miles</span><span>Minutes</span><span>RPE</span><span />
                    </div>
                    {day.activities.map((a, ai) => {
                      const kinds = a.session_type === "basketball" ? BASKETBALL_LABELS : a.session_type === "running" ? RUN_TYPE_LABELS : null;
                      const kindValue = a.session_type === "basketball" ? a.subtype : a.run_type;
                      return (
                        <div key={ai} className="grid grid-cols-[7rem_8rem_4.5rem_4.5rem_4rem_1.25rem] items-center gap-1.5" title={a.source ? `From: "${a.source}"` : undefined}>
                          <span className="text-xs" style={{ color: "var(--text-primary)" }}>
                            {SESSION_LABELS[a.session_type]}
                          </span>
                          {kinds ? (
                            <select
                              value={kindValue ?? ""}
                              onChange={(e) =>
                                setActivity(
                                  ai,
                                  a.session_type === "basketball"
                                    ? { subtype: (e.target.value || "practice") as ImportActivity["subtype"] }
                                    : { run_type: (e.target.value || null) as ImportActivity["run_type"] },
                                )
                              }
                              aria-label="Kind"
                              className={small}
                              style={inputStyle}
                            >
                              {a.session_type === "running" && <option value="">Not specified</option>}
                              {Object.entries(kinds).map(([k, v]) => (
                                <option key={k} value={k}>
                                  {v}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span />
                          )}
                          {a.session_type === "running" || a.session_type === "conditioning" ? (
                            <NumberCell value={a.distance_miles} onChange={(v) => setActivity(ai, { distance_miles: v })} label="Miles" />
                          ) : (
                            <span />
                          )}
                          <NumberCell value={a.duration_minutes} onChange={(v) => setActivity(ai, { duration_minutes: v })} label="Minutes" />
                          <NumberCell value={a.rpe} onChange={(v) => setActivity(ai, { rpe: v })} label="RPE" step="0.5" />
                          <button onClick={() => removeActivity(ai)} aria-label={`Remove ${SESSION_LABELS[a.session_type]}`} style={{ color: "var(--text-muted)" }}>
                            <X size={13} />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </section>
          )}

          {(day.body_weight != null || day.recovery) && (
            <section className="flex flex-wrap gap-6">
              {day.body_weight != null && (
                <div className="flex flex-col gap-1">
                  <SectionToggle checked={day.include_body} onChange={(v) => set({ include_body: v })} label="Body weight" existing={day.existing?.body} />
                  {day.include_body && (
                    <div className="w-24">
                      <NumberCell value={day.body_weight} onChange={(v) => set({ body_weight: v })} label="Body weight lb" />
                    </div>
                  )}
                </div>
              )}
              {day.recovery && (
                <div className="flex flex-col gap-1">
                  <SectionToggle checked={day.include_recovery} onChange={(v) => set({ include_recovery: v })} label="Recovery" existing={day.existing?.recovery} />
                  {day.include_recovery && (
                    <div className="grid grid-cols-4 gap-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
                      {(["sleep_hours", "energy", "soreness", "pain"] as const).map((k) => (
                        <label key={k} className="flex w-20 flex-col gap-0.5">
                          {k === "sleep_hours" ? "Sleep h" : k[0].toUpperCase() + k.slice(1)}
                          <NumberCell
                            value={day.recovery![k]}
                            onChange={(v) => set({ recovery: { ...day.recovery!, [k]: v } })}
                            label={k}
                          />
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </section>
          )}

          {day.notes && (
            <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Notes kept: {day.notes}
            </p>
          )}

          {day.not_imported.length > 0 && (
            <div className="rounded-md border p-2 text-xs" style={{ borderColor: "var(--status-warning)", color: "var(--text-secondary)" }}>
              <p className="mb-1 font-medium" style={{ color: "var(--status-warning)" }}>
                Not imported — check these lines and add anything missing above:
              </p>
              <ul className="list-disc pl-5">
                {day.not_imported.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <button onClick={() => setShowOriginal((v) => !v)} className="flex items-center gap-1 self-start text-xs" style={{ color: "var(--text-muted)" }}>
        {showOriginal ? <ChevronDown size={13} /> : <ChevronRight size={13} />} Original notes
      </button>
      {showOriginal && (
        <pre className="whitespace-pre-wrap rounded-md p-2 text-xs" style={{ background: "var(--surface-2)", color: "var(--text-secondary)" }}>
          {day.original_text}
        </pre>
      )}
    </article>
  );
}
