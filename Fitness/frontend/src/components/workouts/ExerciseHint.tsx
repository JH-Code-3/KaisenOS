import { useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { ExerciseLast, ProgressionRecommendation } from "../../lib/types";
import { formatShortDate } from "../../lib/dates";

const DECISION_COLOR: Record<ProgressionRecommendation["decision"], string> = {
  INCREASE: "var(--status-good)",
  HOLD: "var(--status-warning)",
  REDUCE: "var(--status-critical)",
  "NO DATA": "var(--text-muted)",
};

type HintResult =
  | { status: "first-time" }
  | { status: "ready"; last: ExerciseLast; progression: ProgressionRecommendation }
  | { status: "error" };

/**
 * Shows what was done last time for an exercise and the rule-based
 * progression call (increase / hold / reduce) from the backend.
 */
export function ExerciseHint({ exerciseName }: { exerciseName: string }) {
  // Result is tagged with the name it was fetched for; a mismatch means
  // a newer lookup is still in flight.
  const [result, setResult] = useState<{ name: string; hint: HintResult } | null>(null);

  useEffect(() => {
    let cancelled = false;
    const name = encodeURIComponent(exerciseName);

    Promise.all([
      api.get<ExerciseLast>(`/api/workouts/exercises/${name}/last`),
      api.get<ProgressionRecommendation>(`/api/workouts/exercises/${name}/progression`),
    ])
      .then(([last, progression]) => {
        if (!cancelled) setResult({ name: exerciseName, hint: { status: "ready", last, progression } });
      })
      .catch((err: ApiError) => {
        if (!cancelled)
          setResult({ name: exerciseName, hint: { status: err.status === 404 ? "first-time" : "error" } });
      });

    return () => {
      cancelled = true;
    };
  }, [exerciseName]);

  const hint = result?.name === exerciseName ? result.hint : null;

  if (!hint) {
    return <p className="text-xs" style={{ color: "var(--text-muted)" }}>Checking last session&hellip;</p>;
  }

  if (hint.status === "first-time") {
    return <p className="text-xs" style={{ color: "var(--text-muted)" }}>First time logging this exercise.</p>;
  }

  if (hint.status === "error") {
    return <p className="text-xs" style={{ color: "var(--text-muted)" }}>Couldn&rsquo;t load history.</p>;
  }

  const { last, progression } = hint;
  const topSet =
    last.weight != null && last.reps != null
      ? `${last.weight} lb × ${last.reps}`
      : last.reps != null
        ? `${last.reps} reps`
        : "logged";

  return (
    <div className="flex flex-col gap-0.5 text-xs">
      <p style={{ color: "var(--text-secondary)" }}>
        Last: {topSet}
        {last.sets ? ` · ${last.sets} set${last.sets === 1 ? "" : "s"}` : ""}
        {last.rpe != null ? ` · RPE ${last.rpe}` : ""} · {formatShortDate(last.date)}
      </p>
      <p>
        <span className="font-semibold" style={{ color: DECISION_COLOR[progression.decision] }}>
          {progression.decision}
        </span>{" "}
        <span style={{ color: "var(--text-muted)" }}>{progression.reason}</span>
      </p>
    </div>
  );
}
