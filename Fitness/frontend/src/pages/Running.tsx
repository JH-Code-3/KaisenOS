import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Plus } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { AthleticSession, RunningSummary } from "../lib/types";
import { formatShortDate } from "../lib/dates";
import { BASKETBALL_LABELS, formatDuration, formatPace, RUN_TYPE_LABELS, SESSION_LABELS } from "../lib/running";
import { cardStyle, primaryButton, scrollToTop } from "../lib/ui";
import { StatCard } from "../components/StatCard";
import { WeeklyBarChart } from "../components/charts/WeeklyBarChart";
import { TrendLineChart } from "../components/charts/TrendLineChart";
import { EntryTable } from "../components/checkin/EntryTable";
import { LogSessionForm } from "../components/running/LogSessionForm";
import { GarminActivities } from "../components/garmin/GarminActivities";

const EFFORT = [
  { key: "easy", label: "Easy", color: "var(--series-3)" },
  { key: "moderate", label: "Moderate", color: "var(--series-4)" },
  { key: "hard", label: "Hard", color: "var(--series-2)" },
  { key: "unknown", label: "Not rated", color: "var(--text-muted)" },
] as const;

function describe(s: AthleticSession): string {
  switch (s.session_type) {
    case "running":
    case "conditioning": {
      const parts = [];
      if (s.distance_miles) parts.push(`${s.distance_miles} mi`);
      if (s.duration_minutes) parts.push(formatDuration(s.duration_minutes));
      if (s.pace_per_mile) parts.push(`${formatPace(s.pace_per_mile)} /mi`);
      return parts.join(" · ");
    }
    case "sprint":
      return [
        s.sprint_distance_yards ? `${s.sprint_distance_yards} yd` : null,
        s.sprint_time_seconds ? `${s.sprint_time_seconds} s best` : null,
        s.reps ? `× ${s.reps}` : null,
      ]
        .filter(Boolean)
        .join(" · ");
    case "agility":
      return [s.sprint_time_seconds ? `${s.sprint_time_seconds} s best` : null, s.reps ? `× ${s.reps}` : null].filter(Boolean).join(" · ");
    case "plyometric":
      return [s.jump_height_inches ? `${s.jump_height_inches} in best` : null, s.reps ? `${s.reps} contacts` : null].filter(Boolean).join(" · ");
    case "basketball": {
      const load = s.rpe != null && s.duration_minutes ? Math.round(s.rpe * s.duration_minutes) : null;
      return [s.duration_minutes ? `${Math.round(s.duration_minutes)} min` : null, load != null ? `load ${load}` : null]
        .filter(Boolean)
        .join(" · ");
    }
  }
}

export function Running() {
  const [sessions, setSessions] = useState<AthleticSession[] | null>(null);
  const [summary, setSummary] = useState<RunningSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<{ open: boolean; editing: AthleticSession | null }>({ open: false, editing: null });
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([api.get<AthleticSession[]>("/api/running/sessions?limit=200"), api.get<RunningSummary>("/api/running/summary")])
      .then(([list, sum]) => {
        setSessions(list);
        setSummary(sum);
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, []);
  useEffect(refresh, [refresh]);

  async function remove(s: AthleticSession) {
    try {
      await api.delete(`/api/running/sessions/${s.id}`);
      setNotice("Session deleted.");
      refresh();
    } catch (err) {
      setNotice(err instanceof ApiError ? `Couldn't delete: ${err.message}` : "Couldn't delete.");
    }
  }

  if (error) {
    return (
      <div className="flex items-start gap-2 rounded-lg border p-4 text-sm" style={{ ...cardStyle, borderColor: "var(--status-critical)" }}>
        <AlertTriangle size={16} style={{ color: "var(--status-critical)" }} />
        <div>
          <p className="font-medium" style={{ color: "var(--text-primary)" }}>
            Can&rsquo;t reach the backend
          </p>
          <p style={{ color: "var(--text-secondary)" }}>{error}</p>
        </div>
      </div>
    );
  }
  if (!sessions || !summary) {
    return <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>;
  }

  const weeks = summary.weekly_mileage;
  const thisWeek = weeks[weeks.length - 1];
  const lastWeek = weeks[weeks.length - 2];
  const split = summary.intensity_split;
  const splitTotal = Object.values(split.miles).reduce((a, b) => a + b, 0);
  const bests = summary.bests;
  const load = summary.load;
  const LOAD_STATUS = {
    spike: { text: "Spike", color: "var(--status-serious)" },
    low: { text: "Lower than usual", color: "var(--text-muted)" },
    ok: { text: "Steady", color: "var(--status-good)" },
  } as const;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            Sports &amp; Running
          </h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Practices, games, runs, sprints, jumps, agility and conditioning.
          </p>
        </div>
        {!form.open && (
          <button
            onClick={() => {
              setForm({ open: true, editing: null });
              setNotice(null);
            }}
            className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium"
            style={primaryButton}
          >
            <Plus size={15} /> Log session
          </button>
        )}
      </div>

      {notice && (
        <p className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
          <CheckCircle2 size={15} style={{ color: "var(--status-good)" }} /> {notice}
        </p>
      )}

      {form.open && (
        <LogSessionForm
          key={form.editing?.id ?? "new"}
          editing={form.editing}
          onCancel={() => setForm({ open: false, editing: null })}
          onSaved={(msg) => {
            setForm({ open: false, editing: null });
            setNotice(msg);
            refresh();
          }}
        />
      )}

      <GarminActivities
        onAdded={() => {
          setNotice("Added from Garmin.");
          refresh();
        }}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Miles this week"
          value={thisWeek.miles}
          unit="mi"
          sublabel={`${thisWeek.runs} run${thisWeek.runs === 1 ? "" : "s"} · last week ${lastWeek.miles} mi`}
          isEmpty={thisWeek.miles === 0 && lastWeek.miles === 0}
          emptyText="No runs the last 2 weeks"
        />
        <StatCard
          label="Easy miles (28 days)"
          value={split.easy_share_pct ?? "—"}
          unit="%"
          sublabel={`aim for ~${split.target_easy_pct}% easy`}
          isEmpty={split.easy_share_pct == null}
          emptyText="Rate runs to see this"
        />
        <StatCard
          label="Fastest pace (1+ mi)"
          value={bests.fastest_pace?.pace_label ?? "—"}
          unit="/mi"
          sublabel={bests.fastest_pace ? `${bests.fastest_pace.distance_miles} mi · ${formatShortDate(bests.fastest_pace.date)}` : undefined}
          isEmpty={!bests.fastest_pace}
          emptyText="No timed runs yet"
        />
        <StatCard
          label="5K estimate"
          value={summary.five_k_estimate?.label ?? "—"}
          isEstimate={!!summary.five_k_estimate}
          sublabel={
            summary.five_k_estimate
              ? `from ${summary.five_k_estimate.based_on.distance_miles} mi in ${summary.five_k_estimate.based_on.duration}`
              : undefined
          }
          isEmpty={!summary.five_k_estimate}
          emptyText="Needs a timed 2+ mi run"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_2fr]">
        <section className="flex flex-col gap-2 rounded-lg border p-4" style={cardStyle}>
          <h3 className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Training load (basketball + conditioning)
          </h3>
          <p className="tabular-nums" style={{ color: "var(--text-primary)" }}>
            <span className="text-2xl font-semibold">{load.acute_7d.toLocaleString()}</span>{" "}
            <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
              last 7 days
            </span>
          </p>
          <p className="text-sm tabular-nums" style={{ color: "var(--text-secondary)" }}>
            Usual week (4-wk avg): {load.chronic_weekly_avg.toLocaleString()}
            {load.acwr != null && (
              <>
                {" "}
                · ratio <strong style={{ color: "var(--text-primary)" }}>{load.acwr}</strong>{" "}
                {load.status && (
                  <span className="inline-flex items-center gap-1" style={{ color: LOAD_STATUS[load.status].color }}>
                    {load.status === "spike" ? <AlertTriangle size={13} /> : <CheckCircle2 size={13} />}
                    {LOAD_STATUS[load.status].text}
                  </span>
                )}
              </>
            )}
          </p>
          {load.status === "spike" && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              This week is over 1.5× your usual load. Sudden jumps like this raise injury risk, so go lighter on lifting and running
              until it settles.
            </p>
          )}
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Load = RPE × minutes for each session (basketball, runs, conditioning).
            {load.unrated_sessions_28d > 0 && ` ${load.unrated_sessions_28d} recent session(s) have no RPE or minutes, so they don't count.`}
          </p>
        </section>
        <WeeklyBarChart
          title="Weekly load — last 8 weeks"
          unit="load"
          emptyText="Log basketball or runs with minutes and RPE to see load."
          data={load.weekly.map((w) => ({
            label: formatShortDate(w.week_start).replace(/^\w+, /, ""),
            value: w.basketball + w.other,
            detail: `basketball ${w.basketball} (${w.basketball_sessions} sessions, ${w.basketball_minutes} min), other ${w.other}`,
          }))}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <WeeklyBarChart
          title="Weekly running miles — last 8 weeks"
          unit="mi"
          emptyText="No runs in the last 8 weeks."
          data={weeks.map((w) => ({
            label: formatShortDate(w.week_start).replace(/^\w+, /, ""),
            value: w.miles,
            detail: `${w.runs} run${w.runs === 1 ? "" : "s"}, longest ${w.long_run} mi`,
          }))}
        />
        <TrendLineChart
          title="Pace per run (min/mi, faster is higher)"
          data={summary.pace_points.map((p) => ({ date: p.date, pace: p.pace }))}
          series={[{ key: "pace", label: "Pace", color: "var(--series-1)" }]}
          unit="/mi"
          formatValue={formatPace}
          invertY
          emptyText="No timed runs yet."
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
          <h3 className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Effort mix — last {split.window_days} days (by miles)
          </h3>
          {splitTotal === 0 ? (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              No runs in the last {split.window_days} days.
            </p>
          ) : (
            <>
              <div className="flex h-3 overflow-hidden rounded-full" role="img" aria-label="Share of miles by effort">
                {EFFORT.filter((e) => split.miles[e.key] > 0).map((e, i) => (
                  <div
                    key={e.key}
                    style={{
                      width: `${(split.miles[e.key] / splitTotal) * 100}%`,
                      background: e.color,
                      marginLeft: i ? 2 : 0,
                    }}
                  />
                ))}
              </div>
              <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                {EFFORT.map((e) => (
                  <li key={e.key} className="flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: e.color }} />
                    {e.label} {split.miles[e.key]} mi
                  </li>
                ))}
              </ul>
              {split.status === "too_hard" && (
                <p className="flex items-start gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
                  <AlertTriangle size={14} style={{ color: "var(--status-warning)", flexShrink: 0, marginTop: 3 }} />
                  Only {split.easy_share_pct}% of your miles were easy. Most runners improve faster with ~{split.target_easy_pct}% easy and a
                  couple of quality sessions a week.
                </p>
              )}
              {split.miles.unknown > 0 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Set the kind of run or an RPE so every run counts here.
                </p>
              )}
            </>
          )}
        </section>

        <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
          <h3 className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Personal bests
          </h3>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt style={{ color: "var(--text-muted)" }}>Longest run</dt>
            <dd className="tabular-nums" style={{ color: "var(--text-primary)" }}>
              {bests.longest_run ? `${bests.longest_run.distance_miles} mi · ${formatShortDate(bests.longest_run.date)}` : "—"}
            </dd>
            {bests.sprints.map((sp) => (
              <div key={sp.distance_yards} className="contents">
                <dt style={{ color: "var(--text-muted)" }}>{sp.distance_yards} yd sprint</dt>
                <dd className="tabular-nums" style={{ color: "var(--text-primary)" }}>
                  {sp.time_seconds} s · {formatShortDate(sp.date)}
                </dd>
              </div>
            ))}
            <dt style={{ color: "var(--text-muted)" }}>Best jump</dt>
            <dd className="tabular-nums" style={{ color: "var(--text-primary)" }}>
              {bests.best_jump ? `${bests.best_jump.inches} in · ${formatShortDate(bests.best_jump.date)}` : "—"}
            </dd>
            {summary.avg_easy_pace_28d && (
              <>
                <dt style={{ color: "var(--text-muted)" }}>Avg easy pace (28 d)</dt>
                <dd className="tabular-nums" style={{ color: "var(--text-primary)" }}>
                  {summary.avg_easy_pace_28d} /mi
                </dd>
              </>
            )}
          </dl>
        </section>
      </div>

      <EntryTable
        title="History"
        rows={sessions}
        rowKey={(s) => `${s.source}-${s.id}`}
        readOnlyNote={(s) => (s.source === "legacy" ? "from CLI coach" : null)}
        rowLabel={(s) => `${SESSION_LABELS[s.session_type].toLowerCase()} on ${formatShortDate(s.session_date)}`}
        onEdit={(s) => {
          setForm({ open: true, editing: s });
          setNotice(null);
          scrollToTop();
        }}
        onDelete={remove}
        emptyText="No sessions yet. Use Log session to add one."
        columns={[
          { label: "Date", render: (s) => formatShortDate(s.session_date) },
          {
            label: "Type",
            render: (s) =>
              s.session_type === "running" && s.run_type
                ? `${SESSION_LABELS.running} · ${RUN_TYPE_LABELS[s.run_type]}`
                : s.session_type === "basketball" && s.subtype
                  ? `${SESSION_LABELS.basketball} · ${BASKETBALL_LABELS[s.subtype]}`
                  : SESSION_LABELS[s.session_type],
          },
          { label: "Details", render: describe },
          { label: "RPE", render: (s) => s.rpe ?? "—", align: "right" },
          { label: "Notes", render: (s) => s.notes ?? "" },
        ]}
      />
    </div>
  );
}
