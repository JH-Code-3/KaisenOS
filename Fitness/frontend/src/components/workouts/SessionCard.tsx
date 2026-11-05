import { useState } from "react";
import { Trash2 } from "lucide-react";
import type { WorkoutSession, WorkoutSet } from "../../lib/types";
import { formatShortDate } from "../../lib/dates";

function formatSet(s: WorkoutSet): string {
  const load = s.weight != null ? `${s.weight}` : "BW";
  const reps = s.reps != null ? `×${s.reps}` : "";
  const rpe = s.rpe != null ? ` @${s.rpe}` : "";
  return `${load}${reps}${rpe}`;
}

interface Props {
  session: WorkoutSession;
  onDelete: (session: WorkoutSession) => Promise<void>;
}

export function SessionCard({ session, onDelete }: Props) {
  const [deleting, setDeleting] = useState(false);

  // Keep the order exercises were logged in (sets come back sorted by name).
  const setsByExercise = new Map<string, WorkoutSet[]>();
  [...session.sets]
    .sort((a, b) => a.id - b.id)
    .forEach((s) => setsByExercise.set(s.exercise_name, [...(setsByExercise.get(s.exercise_name) ?? []), s]));

  const stats = new Map((session.analysis?.exercises ?? []).map((e) => [e.exercise, e]));
  const totalVolume = (session.analysis?.exercises ?? []).reduce((sum, e) => sum + e.total_volume, 0);

  async function handleDelete() {
    const label = session.name ?? formatShortDate(session.session_date);
    if (!window.confirm(`Delete "${label}" and all ${session.sets.length} of its sets? This can't be undone.`)) return;
    setDeleting(true);
    try {
      await onDelete(session);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <article
      className="flex flex-col gap-3 rounded-lg border p-4"
      style={{ borderColor: "var(--border-hairline)", background: "var(--surface-1)", opacity: deleting ? 0.5 : 1 }}
    >
      <header className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            {session.name ?? "Workout"}
          </h3>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {formatShortDate(session.session_date)} · {session.sets.length} set{session.sets.length === 1 ? "" : "s"}
            {totalVolume > 0 ? ` · ${Math.round(totalVolume).toLocaleString()} lb volume` : ""}
          </p>
        </div>
        <button
          onClick={handleDelete}
          disabled={deleting}
          aria-label="Delete session"
          title="Delete session"
          style={{ color: "var(--text-muted)" }}
        >
          <Trash2 size={15} />
        </button>
      </header>

      {session.sets.length === 0 && (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          No sets in this session.
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {[...setsByExercise.entries()].map(([exerciseName, sets]) => {
          const stat = stats.get(exerciseName);
          return (
            <li key={exerciseName} className="flex flex-col gap-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  {exerciseName}
                </span>
                {stat?.best_e1rm != null && (
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    est. 1RM {stat.best_e1rm} lb
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {sets.map((s) => (
                  <span
                    key={s.id}
                    className="rounded px-1.5 py-0.5 text-xs tabular-nums"
                    style={{ background: "var(--surface-2)", color: "var(--text-secondary)" }}
                    title={s.pain ? `Pain ${s.pain}/10` : undefined}
                  >
                    {formatSet(s)}
                    {s.pain ? <span style={{ color: "var(--status-serious)" }}> · pain {s.pain}</span> : null}
                  </span>
                ))}
              </div>
            </li>
          );
        })}
      </ul>

      {session.notes && (
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {session.notes}
        </p>
      )}
    </article>
  );
}
