import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleAlert, OctagonAlert, PauseCircle } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { RecoveryEntry, RecoveryStatus } from "../lib/types";
import { formatShortDate, shiftDate, todayLocal } from "../lib/dates";
import { cardStyle, scrollToTop } from "../lib/ui";
import { CheckInForm, type CheckInField } from "../components/checkin/CheckInForm";
import { EntryTable } from "../components/checkin/EntryTable";
import { TrendLineChart } from "../components/charts/TrendLineChart";
import { GarminPanel } from "../components/garmin/GarminPanel";

type RecoveryKey = "sleep_hours" | "energy" | "soreness" | "pain";

const FIELDS: CheckInField<RecoveryKey>[] = [
  { key: "sleep_hours", label: "Sleep (hours)", min: 0, max: 24, step: "0.25", placeholder: "e.g. 7.5" },
  { key: "energy", label: "Energy (0–10)", min: 0, max: 10, step: "1", placeholder: "10 = great" },
  { key: "soreness", label: "Soreness (0–10)", min: 0, max: 10, step: "1", placeholder: "10 = very sore" },
  { key: "pain", label: "Pain (0–10)", min: 0, max: 10, step: "1", placeholder: "0 = none" },
];

// Status colors are reserved for state and always ship with an icon + label.
const STATUS_DISPLAY = {
  ok: { label: "Ready to progress", color: "var(--status-good)", Icon: CheckCircle2 },
  hold: { label: "Hold loads — don't add weight", color: "var(--status-warning)", Icon: PauseCircle },
  reduce: { label: "Back off — reduce load", color: "var(--status-critical)", Icon: OctagonAlert },
  no_data: { label: "No check-ins yet", color: "var(--text-muted)", Icon: CircleAlert },
  stale: { label: "No recent check-in", color: "var(--text-muted)", Icon: CircleAlert },
} as const;

const CHART_DAYS = 30;

const fmt = (v: number | null, suffix = "") => (v == null ? "—" : `${v}${suffix}`);

export function Recovery() {
  const [entries, setEntries] = useState<RecoveryEntry[] | null>(null);
  const [status, setStatus] = useState<RecoveryStatus | null>(null);
  const [date, setDate] = useState(todayLocal());
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([api.get<RecoveryEntry[]>("/api/recovery?limit=90"), api.get<RecoveryStatus>("/api/recovery/status")])
      .then(([list, st]) => {
        setEntries(list);
        setStatus(st);
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, []);

  useEffect(refresh, [refresh]);

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

  if (!entries || !status) {
    return <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>;
  }

  // Newest first from the API; the newest entry for a date wins.
  const existing = entries.find((e) => e.recovery_date === date) ?? null;

  async function save(values: Record<RecoveryKey, number | null>, notes: string | null) {
    const body = { recovery_date: date, ...values, notes };
    if (existing) await api.put(`/api/recovery/${existing.id}`, body);
    else await api.post("/api/recovery", body);
    setNotice(`Check-in for ${formatShortDate(date)} saved.`);
    refresh();
  }

  async function remove(entry: RecoveryEntry) {
    try {
      await api.delete(`/api/recovery/${entry.id}`);
      setNotice(`Check-in for ${formatShortDate(entry.recovery_date)} deleted.`);
      refresh();
    } catch (err) {
      setNotice(err instanceof ApiError ? `Couldn't delete: ${err.message}` : "Couldn't delete.");
    }
  }

  // Chart: one point per day (latest entry per date), last 30 days, oldest -> newest.
  const cutoffIso = shiftDate(todayLocal(), -(CHART_DAYS - 1));
  const seen = new Set<string>();
  const chartRows = entries
    .filter((e) => e.recovery_date >= cutoffIso && !seen.has(e.recovery_date) && seen.add(e.recovery_date))
    .reverse()
    .map((e) => ({
      date: e.recovery_date,
      sleep_hours: e.sleep_hours,
      energy: e.energy,
      soreness: e.soreness,
      pain: e.pain,
    }));

  const display = STATUS_DISPLAY[status.status];
  const stale = status.days_old != null && status.days_old > 1;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Recovery
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          A quick daily check-in. Your latest one decides whether workout loads go up, hold, or come down.
        </p>
      </div>

      <section className="flex items-start gap-3 rounded-lg border p-4" style={cardStyle} aria-live="polite">
        <display.Icon size={20} style={{ color: display.color, flexShrink: 0 }} />
        <div className="flex flex-col gap-1">
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            {display.label}
          </p>
          {status.flags.length > 0 && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Because {status.flags.map((f) => f.message).join(", ")}.
            </p>
          )}
          {status.status === "ok" && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Sleep, energy, soreness and pain are all within range.
            </p>
          )}
          {status.latest && (
            <p className="text-xs" style={{ color: stale ? "var(--status-warning)" : "var(--text-muted)" }}>
              Based on your check-in from {formatShortDate(status.latest.recovery_date)}
              {stale
                ? ` — ${status.days_old} days ago. That's too old to affect today's training; check in for an up-to-date call.`
                : "."}
            </p>
          )}
          {status.status === "no_data" && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Log a check-in below so workout recommendations can account for recovery.
            </p>
          )}
        </div>
      </section>

      {notice && (
        <p className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
          <CheckCircle2 size={15} style={{ color: "var(--status-good)" }} /> {notice}
        </p>
      )}

      <CheckInForm
        title="Daily check-in"
        fields={FIELDS}
        date={date}
        onDateChange={(d) => {
          setDate(d);
          setNotice(null);
        }}
        existing={existing}
        requireOneMessage="Fill in at least one measurement."
        onSave={save}
      />

      <GarminPanel />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <TrendLineChart
          title={`Sleep — last ${CHART_DAYS} days · dashed line = 6 h minimum`}
          data={chartRows}
          series={[{ key: "sleep_hours", label: "Sleep", color: "var(--series-1)" }]}
          unit="h"
          yDomain={[0, 12]}
          reference={{ y: 6 }}
          emptyText="No sleep logged in the last 30 days."
        />
        <TrendLineChart
          title={`Energy, soreness & pain — last ${CHART_DAYS} days`}
          data={chartRows}
          series={[
            { key: "energy", label: "Energy", color: "var(--series-1)" },
            { key: "soreness", label: "Soreness", color: "var(--series-2)" },
            { key: "pain", label: "Pain", color: "var(--series-3)" },
          ]}
          unit="/ 10"
          yDomain={[0, 10]}
          emptyText="No ratings logged in the last 30 days."
        />
      </div>

      <EntryTable
        title="History"
        rows={entries}
        rowLabel={(e) => `check-in for ${formatShortDate(e.recovery_date)}`}
        onEdit={(e) => {
          setDate(e.recovery_date);
          setNotice(null);
          scrollToTop();
        }}
        onDelete={remove}
        emptyText="No check-ins yet."
        columns={[
          { label: "Date", render: (e) => formatShortDate(e.recovery_date) },
          { label: "Sleep", render: (e) => fmt(e.sleep_hours, " h"), align: "right" },
          { label: "Energy", render: (e) => fmt(e.energy), align: "right" },
          { label: "Soreness", render: (e) => fmt(e.soreness), align: "right" },
          { label: "Pain", render: (e) => fmt(e.pain), align: "right" },
          { label: "Notes", render: (e) => e.notes ?? "" },
        ]}
      />
    </div>
  );
}
