import type { DailyNutritionTotals, NutritionTarget } from "../../lib/types";
import { cardStyle } from "../../lib/ui";

const MACROS = [
  { key: "calories", label: "Calories", unit: "kcal", color: "var(--series-1)" },
  { key: "protein_g", label: "Protein", unit: "g", color: "var(--series-3)" },
  { key: "carbs_g", label: "Carbs", unit: "g", color: "var(--series-4)" },
  { key: "fat_g", label: "Fat", unit: "g", color: "var(--series-5)" },
] as const;

interface Props {
  totals: DailyNutritionTotals;
  target: NutritionTarget | null;
  onEditTargets: () => void;
}

/** Eaten vs. target for each macro, as a labeled bar. */
export function MacroProgress({ totals, target, onEditTargets }: Props) {
  return (
    <section className="flex flex-col gap-4 rounded-lg border p-4" style={cardStyle}>
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          {target ? "Eaten vs. target" : "Eaten"}
        </h2>
        <button onClick={onEditTargets} className="text-xs" style={{ color: "var(--series-1)" }}>
          {target ? "Edit targets" : "Set daily targets"}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {MACROS.map(({ key, label, unit, color }) => {
          const eaten = Math.round(totals[key]);
          const goal = target?.[key] ?? null;
          const pct = goal ? Math.min(100, (eaten / goal) * 100) : 0;
          const diff = goal != null ? Math.round(goal - eaten) : null;

          return (
            <div key={key} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
                  {label}
                </span>
                <span className="text-sm tabular-nums" style={{ color: "var(--text-primary)" }}>
                  <span className="font-semibold">{eaten.toLocaleString()}</span>
                  {goal != null && (
                    <span style={{ color: "var(--text-muted)" }}> / {Math.round(goal).toLocaleString()}</span>
                  )}{" "}
                  <span style={{ color: "var(--text-muted)" }}>{unit}</span>
                </span>
              </div>
              {goal != null && (
                <>
                  <div
                    className="h-2 overflow-hidden rounded-full"
                    style={{ background: "var(--surface-2)" }}
                    role="progressbar"
                    aria-label={`${label} progress`}
                    aria-valuenow={eaten}
                    aria-valuemin={0}
                    aria-valuemax={goal}
                  >
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                  </div>
                  <span className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
                    {diff! >= 0 ? `${diff!.toLocaleString()} ${unit} left` : `${Math.abs(diff!).toLocaleString()} ${unit} over`}
                  </span>
                </>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
