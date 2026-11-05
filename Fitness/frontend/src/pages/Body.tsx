import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { BodyEntry, BodyWeightSummary } from "../lib/types";
import { formatShortDate, shiftDate, todayLocal } from "../lib/dates";
import { scrollToTop, secondaryButton } from "../lib/ui";
import { StatCard } from "../components/StatCard";
import { CheckInForm, type CheckInField } from "../components/checkin/CheckInForm";
import { EntryTable } from "../components/checkin/EntryTable";
import { TrendLineChart } from "../components/charts/TrendLineChart";

type BodyKey = "body_weight" | "body_fat" | "waist";

const FIELDS: CheckInField<BodyKey>[] = [
  { key: "body_weight", label: "Weight (lb)", min: 0, step: "0.1", placeholder: "e.g. 201.4" },
  { key: "body_fat", label: "Body fat (%)", min: 0, max: 100, step: "0.1" },
  { key: "waist", label: "Waist (in)", min: 0, step: "0.25" },
];

const RANGES = [
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
  { label: "All", days: null },
] as const;

const fmt = (v: number | null, suffix = "") => (v == null ? "—" : `${v}${suffix}`);
const signed = (n: number) => `${n > 0 ? "+" : n < 0 ? "−" : "±"}${Math.abs(n)}`;

/** Weigh-ins oldest -> newest (one per date), each with its trailing 7-day average. */
function weightSeries(entries: BodyEntry[], sinceIso: string | null) {
  const byDate = new Map<string, number>();
  for (const e of entries) {
    // entries are newest first, so the first value seen per date wins
    if (e.body_weight != null && !byDate.has(e.metric_date)) byDate.set(e.metric_date, e.body_weight);
  }
  const points = [...byDate.entries()].sort(([a], [b]) => a.localeCompare(b));

  return points
    .map(([date, weight]) => {
      const windowStart = shiftDate(date, -6);
      const window = points.filter(([d]) => d >= windowStart && d <= date).map(([, w]) => w);
      const avg = Math.round((window.reduce((s, w) => s + w, 0) / window.length) * 10) / 10;
      return { date, weight, avg_7d: avg };
    })
    .filter((p) => sinceIso == null || p.date >= sinceIso);
}

export function Body() {
  const [entries, setEntries] = useState<BodyEntry[] | null>(null);
  const [summary, setSummary] = useState<BodyWeightSummary | null>(null);
  const [date, setDate] = useState(todayLocal());
  const [range, setRange] = useState<(typeof RANGES)[number]["days"]>(90);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([api.get<BodyEntry[]>("/api/body?limit=1000"), api.get<BodyWeightSummary | null>("/api/body/summary")])
      .then(([list, s]) => {
        setEntries(list);
        setSummary(s);
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

  if (!entries) {
    return <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>;
  }

  const existing = entries.find((e) => e.metric_date === date) ?? null;
  const latestFat = entries.find((e) => e.body_fat != null);
  const latestWaist = entries.find((e) => e.waist != null);
  const chartRows = weightSeries(entries, range == null ? null : shiftDate(todayLocal(), -(range - 1)));

  async function save(values: Record<BodyKey, number | null>, notes: string | null) {
    const body = { metric_date: date, ...values, notes };
    if (existing) await api.put(`/api/body/${existing.id}`, body);
    else await api.post("/api/body", body);
    setNotice(`Entry for ${formatShortDate(date)} saved.`);
    refresh();
  }

  async function remove(entry: BodyEntry) {
    try {
      await api.delete(`/api/body/${entry.id}`);
      setNotice(`Entry for ${formatShortDate(entry.metric_date)} deleted.`);
      refresh();
    } catch (err) {
      setNotice(err instanceof ApiError ? `Couldn't delete: ${err.message}` : "Couldn't delete.");
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Body Composition
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Daily weight swings a lot — the 7-day average is the number to watch.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Latest weight"
          value={summary?.latest_weight ?? "—"}
          unit="lb"
          sublabel={summary ? formatShortDate(summary.latest_date) : undefined}
          isEmpty={!summary}
          emptyText="No weigh-ins yet"
        />
        <StatCard
          label="7-day average"
          value={summary?.avg_7d ?? "—"}
          unit="lb"
          sublabel={
            summary?.weekly_change != null
              ? `${signed(summary.weekly_change)} lb vs. prior 7 days`
              : summary
                ? `${summary.entries_7d} weigh-in${summary.entries_7d === 1 ? "" : "s"} · need a prior week to compare`
                : undefined
          }
          isEmpty={!summary?.avg_7d}
          emptyText="No weigh-ins yet"
        />
        <StatCard
          label="Body fat"
          value={latestFat?.body_fat ?? "—"}
          unit="%"
          sublabel={latestFat ? formatShortDate(latestFat.metric_date) : undefined}
          isEmpty={!latestFat}
          emptyText="Not logged"
        />
        <StatCard
          label="Waist"
          value={latestWaist?.waist ?? "—"}
          unit="in"
          sublabel={latestWaist ? formatShortDate(latestWaist.metric_date) : undefined}
          isEmpty={!latestWaist}
          emptyText="Not logged"
        />
      </div>

      {notice && (
        <p className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
          <CheckCircle2 size={15} style={{ color: "var(--status-good)" }} /> {notice}
        </p>
      )}

      <CheckInForm
        title="Log measurements"
        fields={FIELDS}
        date={date}
        onDateChange={(d) => {
          setDate(d);
          setNotice(null);
        }}
        existing={existing}
        requireOneMessage="Fill in weight, body fat, or waist."
        onSave={save}
      />

      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Weight trend
          </h2>
          <div className="flex gap-1" role="group" aria-label="Chart range">
            {RANGES.map((r) => (
              <button
                key={r.label}
                onClick={() => setRange(r.days)}
                aria-pressed={range === r.days}
                className="rounded-md px-2.5 py-1 text-xs"
                style={
                  range === r.days
                    ? { background: "var(--text-primary)", color: "var(--surface-0)" }
                    : secondaryButton
                }
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        <TrendLineChart
          title="Body weight (lb)"
          data={chartRows}
          series={[
            { key: "weight", label: "Weigh-in", color: "var(--text-muted)", style: "points" },
            { key: "avg_7d", label: "7-day avg", color: "var(--series-1)" },
          ]}
          unit="lb"
          height={240}
          emptyText="No weigh-ins in this range."
        />
      </section>

      <EntryTable
        title="History"
        rows={entries}
        rowLabel={(e) => `entry for ${formatShortDate(e.metric_date)}`}
        onEdit={(e) => {
          setDate(e.metric_date);
          setNotice(null);
          scrollToTop();
        }}
        onDelete={remove}
        emptyText="No measurements yet."
        columns={[
          { label: "Date", render: (e) => formatShortDate(e.metric_date) },
          { label: "Weight", render: (e) => fmt(e.body_weight, " lb"), align: "right" },
          { label: "Body fat", render: (e) => fmt(e.body_fat, "%"), align: "right" },
          { label: "Waist", render: (e) => fmt(e.waist, " in"), align: "right" },
          { label: "Notes", render: (e) => e.notes ?? "" },
        ]}
      />
    </div>
  );
}
