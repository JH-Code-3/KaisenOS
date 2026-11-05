import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { Overview as OverviewData } from "../lib/types";
import { StatCard } from "../components/StatCard";
import { WeeklyCaloriesChart } from "../components/WeeklyCaloriesChart";
import type { DailyNutritionTotals } from "../lib/types";
import { AlertTriangle } from "lucide-react";

export function Overview() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [weekDays, setWeekDays] = useState<DailyNutritionTotals[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<OverviewData>("/api/overview")
      .then(setOverview)
      .catch((err: ApiError) => setError(err.message));

    api
      .get<{ days: DailyNutritionTotals[] }>("/api/nutrition/weekly-average")
      .then((res) => setWeekDays(res.days))
      .catch(() => setWeekDays([]));
  }, []);

  if (error) {
    return (
      <div
        className="flex items-start gap-2 rounded-lg border p-4 text-sm"
        style={{ borderColor: "var(--status-critical)", color: "var(--text-primary)", background: "var(--surface-1)" }}
      >
        <AlertTriangle size={16} style={{ color: "var(--status-critical)" }} />
        <div>
          <p className="font-medium">Can&rsquo;t reach the backend</p>
          <p style={{ color: "var(--text-secondary)" }}>{error}</p>
          <p className="mt-1" style={{ color: "var(--text-muted)" }}>
            Start it from Fitness/ with: <code>.venv/bin/uvicorn backend.main:app --port 8000</code>
          </p>
        </div>
      </div>
    );
  }

  if (!overview) {
    return <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>;
  }

  const recentSession = overview.recent_workout_session;
  const recentExercise = recentSession?.analysis?.exercises?.[0];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Overview
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          {overview.date}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Calories today"
          value={Math.round(overview.todays_nutrition.calories)}
          unit="kcal"
          isEmpty={overview.todays_nutrition.calories === 0}
          emptyText="Nothing logged today"
        />
        <StatCard
          label="Protein today"
          value={Math.round(overview.todays_nutrition.protein_g)}
          unit="g"
          isEmpty={overview.todays_nutrition.calories === 0}
          emptyText="Nothing logged today"
        />
        <StatCard
          label="Body weight"
          value={overview.latest_body_weight?.body_weight ?? "—"}
          unit={overview.latest_body_weight ? "lb" : undefined}
          sublabel={overview.latest_body_weight ? `as of ${overview.latest_body_weight.date}` : undefined}
          isEmpty={!overview.latest_body_weight}
          emptyText="No body weight logged"
        />
        <StatCard
          label="Last night's sleep"
          value={overview.latest_recovery?.sleep_hours ?? "—"}
          unit={overview.latest_recovery?.sleep_hours != null ? "hrs" : undefined}
          sublabel={overview.latest_recovery ? `as of ${overview.latest_recovery.recovery_date}` : undefined}
          isEmpty={!overview.latest_recovery || overview.latest_recovery.sleep_hours == null}
          emptyText="No recovery logged"
        />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Most recent workout"
          value={recentSession ? recentSession.name ?? recentSession.session_date : "—"}
          sublabel={recentSession ? recentSession.session_date : undefined}
          isEmpty={!recentSession}
          emptyText="No workouts logged"
        />
        <StatCard
          label="Top set volume"
          value={recentExercise ? recentExercise.total_volume : "—"}
          unit={recentExercise ? "lb (vol.)" : undefined}
          sublabel={recentExercise ? recentExercise.exercise : undefined}
          isEmpty={!recentExercise}
          emptyText="No sets logged"
        />
        <StatCard
          label="Est. 1RM (top set)"
          value={recentExercise?.best_e1rm ?? "—"}
          unit={recentExercise?.best_e1rm != null ? "lb" : undefined}
          isEstimate={recentExercise?.best_e1rm != null}
          isEmpty={!recentExercise || recentExercise.best_e1rm == null}
          emptyText="No sets logged"
        />
        <StatCard
          label="Weekly training volume"
          value={overview.weekly_training_volume.total_volume}
          unit="lb"
          sublabel={`${overview.weekly_training_volume.session_count} session(s) this week`}
          isEmpty={overview.weekly_training_volume.session_count === 0}
          emptyText="No sessions this week"
        />
      </div>

      {weekDays && <WeeklyCaloriesChart days={weekDays} />}
    </div>
  );
}
