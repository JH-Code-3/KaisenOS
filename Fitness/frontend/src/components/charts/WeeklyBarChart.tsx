import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cardStyle } from "../../lib/ui";

interface Props {
  title: string;
  data: { label: string; value: number; detail?: string }[];
  unit: string;
  emptyText: string;
  height?: number;
}

/** Single-series bar chart (one bar per period) with a hover tooltip. */
export function WeeklyBarChart({ title, data, unit, emptyText, height = 180 }: Props) {
  const hasData = data.some((d) => d.value > 0);

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
      <h3 className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        {title}
      </h3>
      {!hasData ? (
        <div className="flex items-center justify-center text-sm" style={{ height, color: "var(--text-muted)" }}>
          {emptyText}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--gridline)" />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={{ stroke: "var(--baseline)" }}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
            />
            <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--text-muted)", fontSize: 12 }} width={44} />
            <Tooltip
              cursor={{ fill: "var(--surface-2)" }}
              formatter={(value, _name, item) => [
                `${value} ${unit}${item?.payload?.detail ? ` · ${item.payload.detail}` : ""}`,
                title.split(" —")[0],
              ]}
              contentStyle={{
                background: "var(--surface-2)",
                border: "1px solid var(--border-hairline)",
                borderRadius: 6,
                color: "var(--text-primary)",
                fontSize: 12,
              }}
              labelStyle={{ color: "var(--text-secondary)" }}
            />
            <Bar dataKey="value" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
