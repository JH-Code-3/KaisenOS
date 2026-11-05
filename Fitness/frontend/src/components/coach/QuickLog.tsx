import { useState } from "react";
import { CheckCircle2, MessageSquarePlus, Undo2 } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { ImportDay } from "../../lib/types";
import { buildCommit } from "../../lib/importCommit";
import { cardStyle, inputClass, inputStyle, primaryButton, secondaryButton } from "../../lib/ui";
import { ImportDayCard } from "../import/ImportDayCard";
import { CoachText } from "./CoachText";

interface Props {
  enabled: boolean;
  onLogged: () => void;
}

interface Saved {
  batch_id: number;
  meals: number;
  workout_sessions: number;
  activities: number;
}

/** Plain-language summary of what was saved, for the coach's feedback prompt. */
function describe(day: ImportDay): string {
  const parts: string[] = [];
  if (day.include_meals)
    for (const m of day.meals)
      parts.push(
        `${m.meal_type ?? "meal"}: ${m.items.map((i) => `${i.food_name}${i.calories != null ? ` (${Math.round(i.calories)} kcal, ${Math.round(i.protein_g ?? 0)} g protein)` : ""}`).join(", ")}`,
      );
  if (day.include_workouts)
    for (const w of day.workouts)
      parts.push(
        `lifting: ${w.exercises.map((e) => `${e.exercise} ${e.sets}x${e.reps}${e.weight != null ? ` @ ${e.weight} lb` : ""}${e.rpe ? ` RPE ${e.rpe}` : ""}`).join(", ")}`,
      );
  if (day.include_activities)
    for (const a of day.activities)
      parts.push(
        `${a.session_type}${a.subtype ? ` ${a.subtype}` : ""}${a.run_type ? ` (${a.run_type})` : ""}${a.distance_miles ? ` ${a.distance_miles} mi` : ""}${a.duration_minutes ? ` ${a.duration_minutes} min` : ""}${a.rpe != null ? ` RPE ${a.rpe}` : ""}`,
      );
  if (day.include_body && day.body_weight) parts.push(`body weight ${day.body_weight} lb`);
  if (day.include_recovery && day.recovery)
    parts.push(
      `recovery: ${Object.entries(day.recovery)
        .filter(([, v]) => v != null)
        .map(([k, v]) => `${k.replace("_", " ")} ${v}`)
        .join(", ")}`,
    );
  return parts.join("; ");
}

/**
 * "Tell the coach what you ate or did": the local model reads it, you
 * check/edit the result, then it's saved to the right pages and the
 * coach gives quick feedback.
 */
export function QuickLog({ enabled, onLogged }: Props) {
  const [text, setText] = useState("");
  const [day, setDay] = useState<ImportDay | null>(null);
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [saved, setSaved] = useState<Saved | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  async function read() {
    setReading(true);
    setErrors([]);
    setSaved(null);
    setFeedback(null);
    try {
      setDay(await api.post<ImportDay>("/api/coach/log/parse", { text }));
    } catch (err) {
      setErrors([err instanceof ApiError ? err.message : "The coach couldn't read that."]);
    } finally {
      setReading(false);
    }
  }

  async function save() {
    if (!day) return;
    const { days, errors: problems } = buildCommit([day]);
    setErrors(problems);
    if (problems.length) return;
    setSaving(true);
    try {
      const res = await api.post<Saved>("/api/import/commit", { days, source: "coach" });
      setSaved(res);
      const summary = describe(day);
      setDay(null);
      setText("");
      onLogged();
      // Quick feedback from the coach on what was just logged.
      setFeedbackLoading(true);
      api
        .post<{ text: string }>("/api/coach/ask", {
          task: "chat",
          question: `I just logged this for ${days[0].date}: ${summary}. In 2-4 short sentences: anything notable (protein/calories left today vs my targets, how the lifts compare to last time, load), and one tip. Don't repeat the whole log back.`,
        })
        .then((r) => setFeedback(r.text))
        .catch(() => setFeedback(null))
        .finally(() => setFeedbackLoading(false));
    } catch (err) {
      setErrors([err instanceof ApiError ? err.message : "Save failed."]);
    } finally {
      setSaving(false);
    }
  }

  async function undo() {
    if (!saved || !window.confirm("Remove what you just logged?")) return;
    await api.post(`/api/import/batches/${saved.batch_id}/undo`, {});
    setSaved(null);
    setFeedback(null);
    onLogged();
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4" style={{ ...cardStyle, borderColor: "var(--series-1)" }}>
      <h2 className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        <MessageSquarePlus size={16} /> Log with the coach
      </h2>

      {!day && (
        <>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            disabled={!enabled || reading}
            placeholder={
              enabled
                ? "What did you eat or do? e.g. “lunch: chicken burrito bowl ~800 cal. benched 155x5x3 @8, then 90 min practice, felt like a 7”"
                : "The local model isn't available — see Settings."
            }
            aria-label="What did you eat or do?"
            className={inputClass}
            style={inputStyle}
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Logs to today unless you say another day (&ldquo;yesterday&rdquo;, &ldquo;Oct 30&rdquo;). You&rsquo;ll check it before it&rsquo;s saved.
            </p>
            <button
              onClick={read}
              disabled={!enabled || reading || !text.trim()}
              className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
              style={primaryButton}
            >
              {reading ? "Reading…" : "Log it"}
            </button>
          </div>
        </>
      )}

      {day && (
        <>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Here&rsquo;s what I understood. Fix anything that&rsquo;s off, then save.
          </p>
          <ImportDayCard day={day} index={0} onChange={setDay} />
          <div className="flex gap-2">
            <button onClick={save} disabled={saving} className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50" style={primaryButton}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button onClick={() => setDay(null)} className="rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
              Back
            </button>
          </div>
        </>
      )}

      {errors.length > 0 && (
        <ul className="list-disc pl-5 text-sm" style={{ color: "var(--status-critical)" }}>
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}

      {saved && (
        <div className="flex flex-col gap-2">
          <p className="flex flex-wrap items-center gap-1.5 text-sm" style={{ color: "var(--text-primary)" }}>
            <CheckCircle2 size={15} style={{ color: "var(--status-good)" }} />
            Logged {[
              saved.meals && `${saved.meals} meal${saved.meals === 1 ? "" : "s"}`,
              saved.workout_sessions && `${saved.workout_sessions} lifting session`,
              saved.activities && `${saved.activities} run/basketball/conditioning`,
            ]
              .filter(Boolean)
              .join(", ") || "it"}
            .
            <button onClick={undo} className="ml-1 flex items-center gap-1 text-xs" style={{ color: "var(--series-1)" }}>
              <Undo2 size={12} /> Undo
            </button>
          </p>
          {feedbackLoading && (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Coach is looking at it&hellip;
            </p>
          )}
          {feedback && <CoachText text={feedback} />}
        </div>
      )}
    </section>
  );
}
