import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Plus } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { WeeklyTrainingVolume, WorkoutSession } from "../lib/types";
import { StatCard } from "../components/StatCard";
import { LogWorkoutForm } from "../components/workouts/LogWorkoutForm";
import { SessionCard } from "../components/workouts/SessionCard";
import { formatShortDate } from "../lib/dates";

export function Workouts() {
  const [sessions, setSessions] = useState<WorkoutSession[] | null>(null);
  const [weekly, setWeekly] = useState<WeeklyTrainingVolume | null>(null);
  const [exerciseNames, setExerciseNames] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([
      api.get<WorkoutSession[]>("/api/workouts/sessions?limit=30"),
      api.get<WeeklyTrainingVolume>("/api/workouts/volume/weekly"),
      api.get<string[]>("/api/workouts/exercises"),
    ])
      .then(([sessionList, weeklyVolume, names]) => {
        setSessions(sessionList);
        setWeekly(weeklyVolume);
        setExerciseNames(names);
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, []);

  useEffect(refresh, [refresh]);

  async function deleteSession(session: WorkoutSession) {
    try {
      await api.delete(`/api/workouts/sessions/${session.id}`);
      setNotice("Session deleted.");
      refresh();
    } catch (err) {
      setNotice(err instanceof ApiError ? `Couldn't delete: ${err.message}` : "Couldn't delete.");
    }
  }

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
        </div>
      </div>
    );
  }

  if (!sessions || !weekly) {
    return <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>;
  }

  const lastSession = sessions[0];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            Workouts
          </h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Log every set. Volume and estimated 1RM are calculated from what you enter.
          </p>
        </div>
        {!showForm && (
          <button
            onClick={() => {
              setShowForm(true);
              setNotice(null);
            }}
            className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium"
            style={{ background: "var(--series-1)", color: "#fff" }}
          >
            <Plus size={15} /> Log workout
          </button>
        )}
      </div>

      {notice && (
        <p className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
          <CheckCircle2 size={15} style={{ color: "var(--status-good)" }} /> {notice}
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Sessions this week"
          value={weekly.session_count}
          sublabel={`${formatShortDate(weekly.window_start)} – ${formatShortDate(weekly.window_end)}`}
          isEmpty={weekly.session_count === 0}
          emptyText="None in the last 7 days"
        />
        <StatCard
          label="Weekly volume"
          value={Math.round(weekly.total_volume).toLocaleString()}
          unit="lb"
          sublabel="weight × reps, completed sets"
          isEmpty={weekly.session_count === 0}
          emptyText="None in the last 7 days"
        />
        <StatCard
          label="Last session"
          value={lastSession ? formatShortDate(lastSession.session_date) : "—"}
          sublabel={lastSession?.name ?? undefined}
          isEmpty={!lastSession}
          emptyText="No sessions logged"
        />
      </div>

      {showForm && (
        <LogWorkoutForm
          exerciseNames={exerciseNames}
          onCancel={() => setShowForm(false)}
          onSaved={(saved) => {
            setShowForm(false);
            setNotice(`Saved ${saved.name ?? "workout"} — ${saved.sets.length} sets.`);
            refresh();
          }}
        />
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          History
        </h2>
        {sessions.length === 0 ? (
          <div
            className="rounded-lg border p-6 text-sm"
            style={{ borderColor: "var(--border-hairline)", background: "var(--surface-1)", color: "var(--text-muted)" }}
          >
            No per-set sessions yet. Use <strong>Log workout</strong> to add your first one.
            Entries logged through the CLI coach still count toward each exercise&rsquo;s history and recommendations.
          </div>
        ) : (
          sessions.map((session) => <SessionCard key={session.id} session={session} onDelete={deleteSession} />)
        )}
      </section>
    </div>
  );
}
