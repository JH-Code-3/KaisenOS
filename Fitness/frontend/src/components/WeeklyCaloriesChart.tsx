import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DailyNutritionTotals } from "../lib/types";

interface Props {
  days: DailyNutritionTotals[];
}

function formatDayLabel(isoDate: string) {
  const d = new Date(`${isoDate}T00:00:00`);
  return d.toLocaleDateString(undefined, { weekday: "short" });
}

export function WeeklyCaloriesChart({ days }: Props) {
  const hasAnyData = days.some((d) => d.calories > 0);

  if (!hasAnyData) {
    return (
      <div
        className="flex h-[180px] items-center justify-center rounded-lg border text-sm"
        style={{ borderColor: "var(--border-hairline)", background: "var(--surface-1)", color: "var(--text-muted)" }}
      >
        No calories logged in the last 7 days yet.
      </div>
    );
  }

  const data = days.map((d) => ({ day: formatDayLabel(d.date), calories: Math.round(d.calories) }));

  return (
    <div
      className="rounded-lg border p-4"
      style={{ borderColor: "var(--border-hairline)", background: "var(--surface-1)" }}
    >
      <p className="mb-3 text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        Calories — last 7 days
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--gridline)" />
          <XAxis
            dataKey="day"
            tickLine={false}
            axisLine={{ stroke: "var(--baseline)" }}
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            width={44}
            tickFormatter={(v: number) => v.toLocaleString()}
          />
          <Tooltip
            cursor={{ fill: "var(--surface-2)" }}
            contentStyle={{
              background: "var(--surface-2)",
              border: "1px solid var(--border-hairline)",
              borderRadius: 6,
              color: "var(--text-primary)",
              fontSize: 12,
            }}
          />
          <Bar dataKey="calories" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
