import { useEffect, useState } from "react";
import { Watch } from "lucide-react";
import { api } from "../../lib/api";
import type { GarminNight } from "../../lib/types";
import { formatShortDate } from "../../lib/dates";
import { cardStyle } from "../../lib/ui";
import { StatCard } from "../StatCard";
import { TrendLineChart } from "../charts/TrendLineChart";

const avg = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

/**
 * Last night + 30-day trend from Garmin (read-only). Renders nothing
 * until Garmin data has been synced and its fields connected.
 */
export function GarminPanel() {
  const [nights, setNights] = useState<GarminNight[] | null>(null);

  useEffect(() => {
    api
      .get<{ nights: GarminNight[] }>("/api/recovery/garmin?days=30")
      .then((r) => setNights(r.nights))
      .catch(() => setNights([]));
  }, []);

  if (!nights || nights.length === 0) return null;

  const last = nights[nights.length - 1];
  const before = nights.slice(-8, -1);
  const hrvBase = avg(before.map((n) => n.hrv_overnight_avg).filter((v): v is number => v != null));
  const rhrBase = avg(before.map((n) => n.resting_hr).filter((v): v is number => v != null));
  const hrvDiff = last.hrv_overnight_avg != null && hrvBase ? Math.round(((last.hrv_overnight_avg - hrvBase) / hrvBase) * 100) : null;
  const rhrDiff = last.resting_hr != null && rhrBase ? Math.round(last.resting_hr - rhrBase) : null;
  const sleepH = last.sleep_seconds != null ? Math.round((last.sleep_seconds / 3600) * 10) / 10 : null;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        <Watch size={15} /> From Garmin
        <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>
          · last night = {formatShortDate(last.date)}
        </span>
      </h2>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Measured sleep"
          value={sleepH ?? "—"}
          unit={sleepH != null ? "h" : undefined}
          sublabel={last.sleep_score != null ? `sleep score ${last.sleep_score}` : undefined}
          isEmpty={sleepH == null}
          emptyText="Not in Garmin data"
        />
        <StatCard
          label="Overnight HRV"
          value={last.hrv_overnight_avg ?? "—"}
          unit={last.hrv_overnight_avg != null ? "ms" : undefined}
          sublabel={
            hrvDiff != null
              ? `${hrvDiff > 0 ? "+" : ""}${hrvDiff}% vs your 7-night average${last.hrv_status ? ` · ${last.hrv_status.toLowerCase()}` : ""}`
              : last.hrv_status ?? undefined
          }
          isEmpty={last.hrv_overnight_avg == null}
          emptyText="Not in Garmin data"
        />
        <StatCard
          label="Resting heart rate"
          value={last.resting_hr ?? "—"}
          unit={last.resting_hr != null ? "bpm" : undefined}
          sublabel={rhrDiff != null ? `${rhrDiff > 0 ? "+" : ""}${rhrDiff} vs your 7-night average` : undefined}
          isEmpty={last.resting_hr == null}
          emptyText="Not in Garmin data"
        />
        <StatCard
          label="Body battery"
          value={last.body_battery_high ?? "—"}
          sublabel={last.body_battery_low != null ? `low ${last.body_battery_low}` : undefined}
          isEmpty={last.body_battery_high == null}
          emptyText="Not in Garmin data"
        />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <TrendLineChart
          title="Garmin sleep — last 30 nights"
          data={nights.map((n) => ({ date: n.date, sleep: n.sleep_seconds != null ? Math.round((n.sleep_seconds / 3600) * 10) / 10 : null }))}
          series={[{ key: "sleep", label: "Sleep", color: "var(--series-1)" }]}
          unit="h"
          yDomain={[0, 12]}
          reference={{ y: 6 }}
          emptyText="No sleep data from Garmin."
        />
        <TrendLineChart
          title="Overnight HRV — last 30 nights"
          data={nights.map((n) => ({ date: n.date, hrv: n.hrv_overnight_avg }))}
          series={[{ key: "hrv", label: "HRV", color: "var(--series-3)" }]}
          unit="ms"
          emptyText="No HRV data from Garmin."
        />
      </div>
      <p className="text-xs" style={{ ...cardStyle, background: "transparent", color: "var(--text-muted)" }}>
        Garmin data is read-only here and comes from your last manual sync. The coach uses it on top of your own check-ins.
      </p>
    </section>
  );
}
