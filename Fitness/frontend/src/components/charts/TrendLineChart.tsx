import {
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cardStyle } from "../../lib/ui";

export interface TrendSeries {
  key: string;
  label: string;
  color: string;
  /** "line" = 2px straight line with dots; "points" = dots only (raw readings). */
  style?: "line" | "points";
}

interface Props {
  title: string;
  /** Rows must include `date` as YYYY-MM-DD; other keys are series values. */
  data: ({ date: string } & Record<string, string | number | null>)[];
  series: TrendSeries[];
  unit?: string;
  /** Fixed y range. Omit to fit the data with a little padding. */
  yDomain?: [number, number];
  /** Dashed guide line; its meaning is described in the chart title. */
  reference?: { y: number };
  height?: number;
  emptyText: string;
  /** Format values for the y-axis and tooltip (e.g. pace "8:30"). */
  formatValue?: (value: number) => string;
  /** Flip the y-axis so lower values sit higher (e.g. pace: faster = up). */
  invertY?: boolean;
}

const MARGIN = { top: 8, right: 72, left: 0, bottom: 0 };
const X_AXIS_HEIGHT = 30;
const LABEL_GAP_PX = 13;

const toTime = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).getTime();
};
const formatTick = (t: number) => new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });
const formatTooltipDate = (t: number) =>
  new Date(t).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });

/**
 * Single-axis line chart on a true time axis (gaps between dates show as
 * gaps). Legend for 2+ series plus a direct label at each line's last
 * point, nudged apart when they'd collide; crosshair tooltip.
 */
export function TrendLineChart({ title, data, series, unit, yDomain, reference, height = 200, emptyText, formatValue, invertY }: Props) {
  const rows: Record<string, string | number | null>[] = data.map((row) => ({ ...row, __t: toTime(row.date) }));
  const values = rows.flatMap((row) => series.map((s) => row[s.key]).filter((v): v is number => typeof v === "number"));
  const hasData = values.length > 0;

  const domain: [number, number] = yDomain ?? (hasData ? [Math.floor(Math.min(...values) - 1), Math.ceil(Math.max(...values) + 1)] : [0, 1]);

  // Direct end labels: place each at its last value, then push apart so
  // none overlap (greedy, top to bottom, in pixels).
  const plotHeight = height - MARGIN.top - X_AXIS_HEIGHT;
  const pxPerUnit = (invertY ? -1 : 1) * (plotHeight / (domain[1] - domain[0] || 1));
  const labelOffsets = new Map<string, { index: number; dy: number }>();
  const ends = series
    .filter((s) => s.style !== "points")
    .map((s) => {
      const index = rows.reduce((last, row, i) => (row[s.key] != null ? i : last), -1);
      const base = invertY ? domain[0] : domain[1];
      return { key: s.key, index, y: index >= 0 ? (base - Number(rows[index][s.key])) * pxPerUnit : 0 };
    })
    .filter((e) => e.index >= 0)
    .sort((a, b) => a.y - b.y);
  let previous = -Infinity;
  for (const end of ends) {
    const placed = Math.max(end.y, previous + LABEL_GAP_PX);
    labelOffsets.set(end.key, { index: end.index, dy: placed - end.y });
    previous = placed;
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          {title}
        </h3>
        {series.length > 1 && hasData && (
          <ul className="flex flex-wrap gap-3 text-xs" style={{ color: "var(--text-secondary)" }}>
            {series.map((s) => (
              <li key={s.key} className="flex items-center gap-1.5">
                <span
                  className="inline-block"
                  style={{
                    width: s.style === "points" ? 8 : 14,
                    height: s.style === "points" ? 8 : 2,
                    borderRadius: s.style === "points" ? 999 : 1,
                    background: s.color,
                  }}
                />
                {s.label}
              </li>
            ))}
          </ul>
        )}
      </div>

      {!hasData ? (
        <div className="flex items-center justify-center text-sm" style={{ height, color: "var(--text-muted)" }}>
          {emptyText}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={rows} margin={MARGIN}>
            <CartesianGrid vertical={false} stroke="var(--gridline)" />
            <XAxis
              dataKey="__t"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={formatTick}
              height={X_AXIS_HEIGHT}
              tickLine={false}
              axisLine={{ stroke: "var(--baseline)" }}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              minTickGap={32}
            />
            <YAxis
              domain={domain}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--text-muted)", fontSize: 12 }}
              width={44}
              allowDecimals={false}
              reversed={invertY}
              tickFormatter={formatValue ? (v: number) => formatValue(v) : undefined}
            />
            {reference && (
              <ReferenceLine
                y={reference.y}
                stroke="var(--text-muted)"
                strokeDasharray="4 4"
              />
            )}
            <Tooltip
              cursor={{ stroke: "var(--baseline)" }}
              labelFormatter={(t) => formatTooltipDate(Number(t))}
              formatter={(value, name) => {
                const shown = formatValue && typeof value === "number" ? formatValue(value) : value;
                return [unit ? `${shown} ${unit}` : shown, name];
              }}
              contentStyle={{
                background: "var(--surface-2)",
                border: "1px solid var(--border-hairline)",
                borderRadius: 6,
                color: "var(--text-primary)",
                fontSize: 12,
              }}
              labelStyle={{ color: "var(--text-secondary)" }}
            />
            {series.map((s) => {
              const isPoints = s.style === "points";
              const endLabel = labelOffsets.get(s.key);
              return (
                <Line
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  type="linear"
                  stroke={isPoints ? "transparent" : s.color}
                  strokeWidth={2}
                  dot={{ r: 4, fill: s.color, stroke: "var(--surface-1)", strokeWidth: 2 }}
                  activeDot={{ r: 5, fill: s.color, stroke: "var(--surface-1)", strokeWidth: 2 }}
                  connectNulls
                  isAnimationActive={false}
                >
                  {endLabel && (
                    <LabelList
                      dataKey={s.key}
                      content={(props) => {
                        if (props.index !== endLabel.index || props.x == null || props.y == null) return null;
                        return (
                          <text
                            x={Number(props.x) + 8}
                            y={Number(props.y) + endLabel.dy}
                            dy={4}
                            fontSize={11}
                            fill="var(--text-secondary)"
                          >
                            {s.label}
                          </text>
                        );
                      }}
                    />
                  )}
                </Line>
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
