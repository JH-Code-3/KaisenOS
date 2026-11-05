import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  CircleAlert,
  HeartPulse,
  Lock,
  OctagonAlert,
  PauseCircle,
  Dumbbell,
  Sparkles,
} from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { CoachInsights, CoachStatus, PlannedExercise, Readiness } from "../lib/types";
import { formatShortDate } from "../lib/dates";
import { cardStyle, secondaryButton } from "../lib/ui";
import { CoachText } from "../components/coach/CoachText";
import { CoachChat } from "../components/coach/CoachChat";
import { QuickLog } from "../components/coach/QuickLog";
import { GarminSyncWarning } from "../components/garmin/GarminSyncWarning";

// Status colors are reserved for state and always paired with an icon + label.
const READINESS: Record<Readiness, { label: string; detail: string; color: string; Icon: typeof CheckCircle2 }> = {
  GO: { label: "Good to train", detail: "Recovery looks fine — progress as planned.", color: "var(--status-good)", Icon: CheckCircle2 },
  HOLD: { label: "Hold loads", detail: "Train, but don't add weight today.", color: "var(--status-warning)", Icon: PauseCircle },
  REDUCE: { label: "Back off", detail: "Go about 10% lighter, or take an easy day.", color: "var(--status-critical)", Icon: OctagonAlert },
  UNKNOWN: {
    label: "No recent recovery data",
    detail: "Log a recovery check-in (or sync Garmin) for a readiness call.",
    color: "var(--text-muted)",
    Icon: CircleAlert,
  },
};

const DECISION_COLOR: Record<string, string> = {
  INCREASE: "var(--status-good)",
  HOLD: "var(--status-warning)",
  REDUCE: "var(--status-critical)",
};

const LOAD_SEVERITY = {
  info: { label: "Note", color: "var(--text-muted)" },
  caution: { label: "Caution", color: "var(--status-warning)" },
  high: { label: "Big jump", color: "var(--status-serious)" },
};

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
      {children}
    </h2>
  );
}

export function Coach() {
  const [insights, setInsights] = useState<CoachInsights | null>(null);
  const [status, setStatus] = useState<CoachStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<{ summary?: string; next_workout?: string; improve?: string }>({});
  const [busy, setBusy] = useState<"summary" | "next_workout" | "improve" | null>(null);
  const [askError, setAskError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([api.get<CoachInsights>("/api/coach/insights"), api.get<CoachStatus>("/api/coach/status")])
      .then(([i, s]) => {
        setInsights(i);
        setStatus(s);
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, []);

  useEffect(refresh, [refresh]);

  async function ask(task: "summary" | "next_workout" | "improve") {
    setBusy(task);
    setAskError(null);
    try {
      const res = await api.post<{ text: string; insights: CoachInsights }>("/api/coach/ask", { task });
      setAnswers((a) => ({ ...a, [task]: res.text }));
      setInsights(res.insights);
    } catch (err) {
      setAskError(err instanceof ApiError ? err.message : "The coach didn't respond.");
    } finally {
      setBusy(null);
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

  if (!insights || !status) {
    return <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>;
  }

  const llmReady = status.model_ready && !status.ollama_error;
  const readiness = READINESS[insights.readiness];
  const [thisWeek, ...priorWeeks] = insights.load_by_week;
  const avg = (key: "lifting_volume_lb" | "running_miles") =>
    priorWeeks.length ? priorWeeks.reduce((s, w) => s + w[key], 0) / priorWeeks.length : 0;
  const plan = insights.next_workout;
  const garmin = status.garmin;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          AI Coach
        </h1>
        <p className="flex flex-wrap items-center gap-1.5 text-sm" style={{ color: "var(--text-muted)" }}>
          <Lock size={13} /> Runs on <strong style={{ color: "var(--text-secondary)" }}>{status.model}</strong> on this
          computer. Your data never leaves it.
        </p>
      </div>

      {!llmReady && (
        <div className="flex items-start gap-2 rounded-lg border p-4 text-sm" style={{ ...cardStyle, borderColor: "var(--status-warning)" }}>
          <AlertTriangle size={16} style={{ color: "var(--status-warning)", flexShrink: 0 }} />
          <div style={{ color: "var(--text-secondary)" }}>
            <p className="font-medium" style={{ color: "var(--text-primary)" }}>
              The local model isn&rsquo;t available
            </p>
            <p>{status.ollama_error ?? `Model "${status.model}" isn't downloaded. Pick another in Settings or run: ollama pull ${status.model}`}</p>
            <p className="mt-1">
              The numbers below still work without it.{" "}
              <Link to="/settings" style={{ color: "var(--series-1)" }}>
                Open Settings
              </Link>
            </p>
          </div>
        </div>
      )}

      <GarminSyncWarning status={status} />

      <QuickLog enabled={llmReady} onLogged={refresh} />

      {insights.safety_notes.map((note) => (
        <div
          key={note}
          role="alert"
          className="flex items-start gap-2 rounded-lg border p-4 text-sm"
          style={{ ...cardStyle, borderColor: "var(--status-critical)" }}
        >
          <HeartPulse size={16} style={{ color: "var(--status-critical)", flexShrink: 0 }} />
          <div>
            <p className="font-medium" style={{ color: "var(--text-primary)" }}>
              Pain logged — get it checked
            </p>
            <p style={{ color: "var(--text-secondary)" }}>{note}</p>
          </div>
        </div>
      ))}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Readiness */}
        <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
          <SectionTitle>Today&rsquo;s readiness</SectionTitle>
          <div className="flex items-start gap-3">
            <readiness.Icon size={22} style={{ color: readiness.color, flexShrink: 0 }} />
            <div>
              <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                {readiness.label}
              </p>
              <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
                {readiness.detail}
              </p>
            </div>
          </div>
          {insights.recovery.flags.length > 0 && (
            <ul className="flex flex-col gap-1 text-sm" style={{ color: "var(--text-secondary)" }}>
              {insights.recovery.flags.map((f) => (
                <li key={f.message} className="flex items-baseline gap-2">
                  <span className="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase" style={{ background: "var(--surface-2)", color: "var(--text-muted)" }}>
                    {f.source}
                  </span>
                  {f.message.charAt(0).toUpperCase() + f.message.slice(1)}
                </li>
              ))}
            </ul>
          )}
          {insights.recovery.notes.map((n) => (
            <p key={n} className="text-xs" style={{ color: "var(--text-muted)" }}>
              {n}{" "}
              <Link to="/recovery" style={{ color: "var(--series-1)" }}>
                Check in
              </Link>
            </p>
          ))}
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Sources: recovery check-ins
            {insights.recovery.garmin_available ? " + Garmin" : " (Garmin not synced — optional)"}
          </p>
        </section>

        {/* Training load */}
        <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
          <SectionTitle>Training load — last 7 days vs. 3-week average</SectionTitle>
          <dl className="grid grid-cols-2 gap-3">
            {(
              [
                ["Lifting volume", "lifting_volume_lb", "lb"],
                ["Running", "running_miles", "mi"],
              ] as const
            ).map(([label, key, unit]) => (
              <div key={key}>
                <dt className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {label}
                </dt>
                <dd className="tabular-nums" style={{ color: "var(--text-primary)" }}>
                  <span className="text-xl font-semibold">{Math.round(thisWeek[key]).toLocaleString()}</span>{" "}
                  <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                    {unit}
                  </span>
                  <span className="block text-xs" style={{ color: "var(--text-muted)" }}>
                    avg {Math.round(avg(key)).toLocaleString()} {unit}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
          {insights.load_flags.length === 0 ? (
            <p className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
              <CheckCircle2 size={14} style={{ color: "var(--status-good)" }} /> No big jumps in training load.
            </p>
          ) : (
            <ul className="flex flex-col gap-1.5 text-sm">
              {insights.load_flags.map((f) => (
                <li key={f.metric} className="flex items-start gap-2" style={{ color: "var(--text-secondary)" }}>
                  <AlertTriangle size={14} style={{ color: LOAD_SEVERITY[f.severity].color, flexShrink: 0, marginTop: 3 }} />
                  <span>
                    <strong style={{ color: "var(--text-primary)" }}>{LOAD_SEVERITY[f.severity].label}:</strong> {f.message}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* Next workout */}
      <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionTitle>Suggested next workout</SectionTitle>
          {plan && (
            <button
              onClick={() => ask("next_workout")}
              disabled={!llmReady || busy !== null}
              className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm disabled:opacity-50"
              style={secondaryButton}
            >
              <Sparkles size={14} /> {busy === "next_workout" ? "Thinking…" : "Explain it"}
            </button>
          )}
        </div>
        {!plan ? (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            No lifting sessions in the last 4 weeks.{" "}
            <Link to="/workouts" style={{ color: "var(--series-1)" }}>
              Log a workout
            </Link>{" "}
            and the coach will plan the next one.
          </p>
        ) : (
          <>
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              <strong style={{ color: "var(--text-primary)" }}>{plan.session_name}</strong> — last done{" "}
              {formatShortDate(plan.last_done)}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[32rem] text-sm">
                <thead>
                  <tr className="text-left text-xs" style={{ color: "var(--text-muted)" }}>
                    <th className="py-1 font-medium">Exercise</th>
                    <th className="py-1 text-right font-medium">Last</th>
                    <th className="py-1 text-right font-medium">Today</th>
                    <th className="py-1 pl-4 font-medium">Call</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums" style={{ color: "var(--text-secondary)" }}>
                  {plan.exercises.map((e: PlannedExercise) => (
                    <tr key={e.exercise} className="border-t align-top" style={{ borderColor: "var(--border-hairline)" }}>
                      <td className="py-1.5" style={{ color: "var(--text-primary)" }}>
                        {e.exercise}
                      </td>
                      <td className="py-1.5 text-right">{e.previous_weight != null ? `${e.previous_weight} lb` : "—"}</td>
                      <td className="py-1.5 text-right font-medium" style={{ color: "var(--text-primary)" }}>
                        {e.recommended_weight != null ? `${e.recommended_weight} lb` : "—"}
                      </td>
                      <td className="py-1.5 pl-4">
                        <span className="font-semibold" style={{ color: DECISION_COLOR[e.decision] ?? "var(--text-muted)" }}>
                          {e.decision}
                        </span>
                        <span className="block text-xs" style={{ color: "var(--text-muted)" }}>
                          {e.reason}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        {answers.next_workout && <CoachText text={answers.next_workout} />}
      </section>

      {/* Lifting intensity */}
      <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionTitle>Lifting intensity — last 4 weeks</SectionTitle>
          {insights.intensity.lifts.length > 0 && (
            <button
              onClick={() => ask("improve")}
              disabled={!llmReady || busy !== null}
              className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm disabled:opacity-50"
              style={secondaryButton}
            >
              <Dumbbell size={14} /> {busy === "improve" ? "Thinking…" : "Coach me on my lifting"}
            </button>
          )}
        </div>
        {insights.intensity.lifts.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            No set-by-set lifting logged in the last 4 weeks. Log workouts or{" "}
            <Link to="/import" style={{ color: "var(--series-1)" }}>
              import your notes
            </Link>
            .
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[44rem] text-sm">
                <thead>
                  <tr className="text-left text-xs" style={{ color: "var(--text-muted)" }}>
                    <th className="py-1 font-medium">Lift</th>
                    <th className="py-1 text-right font-medium">Sets / wk</th>
                    <th className="py-1 text-right font-medium">Avg RPE</th>
                    <th className="py-1 text-right font-medium">Sets RPE 8+</th>
                    <th className="py-1 text-right font-medium">Best est. 1RM</th>
                    <th className="py-1 pl-4 font-medium">Trend</th>
                    <th className="py-1 font-medium">Latest top set</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums" style={{ color: "var(--text-secondary)" }}>
                  {insights.intensity.lifts.map((l) => (
                    <tr key={l.exercise} className="border-t" style={{ borderColor: "var(--border-hairline)" }}>
                      <td className="py-1.5" style={{ color: "var(--text-primary)" }}>
                        {l.exercise}
                      </td>
                      <td className="py-1.5 text-right">{l.sets_per_week}</td>
                      <td className="py-1.5 text-right" title={`RPE logged on ${l.rpe_logged_pct}% of sets`}>
                        {l.avg_rpe ?? "—"}
                      </td>
                      <td className="py-1.5 text-right">{l.hard_set_share_pct != null ? `${l.hard_set_share_pct}%` : "—"}</td>
                      <td className="py-1.5 text-right">{l.best_e1rm != null ? `${Math.round(l.best_e1rm)} lb` : "—"}</td>
                      <td className="py-1.5 pl-4">
                        {l.e1rm_trend ? (
                          <span
                            style={{
                              color:
                                l.e1rm_trend === "improving"
                                  ? "var(--status-good)"
                                  : l.e1rm_trend === "declining"
                                    ? "var(--status-serious)"
                                    : "var(--text-secondary)",
                            }}
                          >
                            {l.e1rm_trend === "improving" ? "▲" : l.e1rm_trend === "declining" ? "▼" : "■"} {l.e1rm_trend}
                            {l.e1rm_change_lb ? ` (${l.e1rm_change_lb > 0 ? "+" : ""}${l.e1rm_change_lb} lb)` : ""}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-1.5">
                        {l.last_top_set ?? "—"}
                        {l.last_top_set_pct_of_best != null && l.last_top_set_pct_of_best < 100 && (
                          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                            {" "}
                            ({l.last_top_set_pct_of_best}% of best)
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-col gap-1.5">
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                Working sets per muscle per week (typical productive range {insights.intensity.sets_range_per_week[0]}–
                {insights.intensity.sets_range_per_week[1]}):
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {insights.intensity.muscle_groups.map((m) => (
                  <li
                    key={m.muscle}
                    className="rounded px-2 py-0.5 text-xs tabular-nums"
                    style={{ background: "var(--surface-2)", color: "var(--text-secondary)" }}
                  >
                    {m.muscle} <strong style={{ color: "var(--text-primary)" }}>{m.working_sets_per_week}</strong>
                    {m.status !== "in range" && (
                      <span style={{ color: "var(--status-warning)" }}> · {m.status}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
        {answers.improve && <CoachText text={answers.improve} />}
      </section>

      {/* Summary */}
      <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionTitle>Last two weeks</SectionTitle>
          <button
            onClick={() => ask("summary")}
            disabled={!llmReady || busy !== null}
            className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm disabled:opacity-50"
            style={secondaryButton}
          >
            <Sparkles size={14} /> {busy === "summary" ? "Thinking…" : answers.summary ? "Refresh summary" : "Summarize my training"}
          </button>
        </div>
        {answers.summary ? (
          <CoachText text={answers.summary} />
        ) : (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            The coach reads your workouts, runs, check-ins, nutrition and body logs{garmin ? " plus Garmin" : ""} and writes a short recap.
          </p>
        )}
      </section>

      {askError && (
        <p className="text-sm" style={{ color: "var(--status-critical)" }}>
          {askError}
        </p>
      )}

      <CoachChat enabled={llmReady} placeholderExamples="“Should I run tomorrow?” or “Why is my bench stalling?”" />
    </div>
  );
}
