import type { ReactNode } from "react";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";

interface StatCardProps {
  label: string;
  value: ReactNode;
  unit?: string;
  sublabel?: string;
  trend?: "up" | "down" | "flat";
  trendIsGood?: boolean;
  isEstimate?: boolean;
  isEmpty?: boolean;
  emptyText?: string;
}

export function StatCard({
  label,
  value,
  unit,
  sublabel,
  trend,
  trendIsGood,
  isEstimate,
  isEmpty,
  emptyText,
}: StatCardProps) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;

  const trendColor =
    trend && trend !== "flat"
      ? trendIsGood
        ? "var(--status-good)"
        : "var(--status-critical)"
      : "var(--text-muted)";

  return (
    <div
      className="flex flex-col gap-1 rounded-lg border p-4"
      style={{ borderColor: "var(--border-hairline)", background: "var(--surface-1)" }}
    >
      <span className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        {label}
      </span>

      {isEmpty ? (
        <span className="text-sm" style={{ color: "var(--text-muted)" }}>
          {emptyText ?? "No data logged yet"}
        </span>
      ) : (
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
            {value}
          </span>
          {unit && (
            <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
              {unit}
            </span>
          )}
          {isEstimate && (
            <span
              className="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase"
              style={{ color: "var(--text-muted)", background: "var(--surface-2)" }}
            >
              est.
            </span>
          )}
        </div>
      )}

      {sublabel && !isEmpty && (
        <div className="flex items-center gap-1 text-xs" style={{ color: trendColor }}>
          {trend && <TrendIcon size={12} />}
          <span style={{ color: trend ? trendColor : "var(--text-secondary)" }}>{sublabel}</span>
        </div>
      )}
    </div>
  );
}
