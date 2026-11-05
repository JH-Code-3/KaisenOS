import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Plus, Watch } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { GarminActivity } from "../../lib/types";
import { formatShortDate } from "../../lib/dates";
import { BASKETBALL_LABELS, RUN_TYPE_LABELS } from "../../lib/running";
import { cardStyle, inputClass, inputStyle, primaryButton } from "../../lib/ui";

interface RowState {
  kind: string;
  rpe: string;
  busy: boolean;
  error: string | null;
}

const small = `${inputClass} px-1.5 py-1 text-xs`;

/**
 * Watch activities that aren't in your log yet. Adding copies the date,
 * minutes and distance from Garmin; you choose the kind and your RPE.
 */
export function GarminActivities({ onAdded }: { onAdded: () => void }) {
  const [items, setItems] = useState<GarminActivity[] | null>(null);
  const [strengthHidden, setStrengthHidden] = useState(0);
  const [rows, setRows] = useState<Record<number, RowState>>({});

  const load = useCallback(() => {
    api
      .get<{ activities: GarminActivity[]; strength_not_shown: number }>("/api/running/garmin?days=30")
      .then((r) => {
        setItems(r.activities);
        setStrengthHidden(r.strength_not_shown);
      })
      .catch(() => setItems([]));
  }, []);
  useEffect(load, [load]);

  if (!items || (items.length === 0 && strengthHidden === 0)) return null;

  const row = (a: GarminActivity): RowState =>
    rows[a.activity_id] ?? { kind: a.maps_to === "basketball" ? "practice" : "", rpe: "", busy: false, error: null };
  const setRow = (id: number, patch: Partial<RowState>) =>
    setRows((r) => ({ ...r, [id]: { ...(r[id] ?? { kind: "", rpe: "", busy: false, error: null }), ...patch } }));

  async function add(a: GarminActivity) {
    const state = row(a);
    const rpe = state.rpe.trim() === "" ? null : Number(state.rpe);
    if (rpe != null && (Number.isNaN(rpe) || rpe < 0 || rpe > 10)) {
      setRow(a.activity_id, { error: "RPE must be 0–10." });
      return;
    }
    setRow(a.activity_id, { ...state, busy: true, error: null });
    try {
      await api.post(`/api/running/garmin/${a.activity_id}`, {
        subtype: a.maps_to === "basketball" ? state.kind || "practice" : null,
        run_type: a.maps_to === "running" && state.kind ? state.kind : null,
        rpe,
      });
      load();
      onAdded();
    } catch (err) {
      setRow(a.activity_id, { busy: false, error: err instanceof ApiError ? err.message : "Couldn't add." });
    }
  }

  async function skip(a: GarminActivity) {
    await api.post(`/api/running/garmin/${a.activity_id}/skip`, {});
    load();
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
      <div>
        <h2 className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          <Watch size={15} /> From your Garmin
          {items.length > 0 && (
            <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>
              · {items.length} not in your log yet (last 30 days)
            </span>
          )}
        </h2>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Adding copies the date, minutes and distance from your watch. Add your RPE (how hard it felt, 0–10) so it counts toward
          your load.
        </p>
      </div>

      {items.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Everything from your watch is in your log.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[46rem] text-sm">
            <thead>
              <tr className="text-left text-xs" style={{ color: "var(--text-muted)" }}>
                <th className="py-1 font-medium">Date</th>
                <th className="py-1 font-medium">Activity</th>
                <th className="py-1 text-right font-medium">Time</th>
                <th className="py-1 text-right font-medium">Avg HR</th>
                <th className="py-1 pl-3 font-medium">Kind</th>
                <th className="py-1 font-medium">RPE</th>
                <th className="py-1" />
              </tr>
            </thead>
            <tbody className="tabular-nums" style={{ color: "var(--text-secondary)" }}>
              {items.map((a) => {
                const state = row(a);
                const kinds = a.maps_to === "basketball" ? BASKETBALL_LABELS : a.maps_to === "running" ? RUN_TYPE_LABELS : null;
                return (
                  <tr key={a.activity_id} className="border-t align-top" style={{ borderColor: "var(--border-hairline)" }}>
                    <td className="py-2">{formatShortDate(a.date)}</td>
                    <td className="py-2" style={{ color: "var(--text-primary)" }}>
                      {a.label}
                      {a.miles ? <span style={{ color: "var(--text-secondary)" }}> · {a.miles} mi</span> : null}
                      {a.possible_duplicate && (
                        <span className="ml-1.5 inline-flex items-center gap-1 text-[11px]" style={{ color: "var(--status-warning)" }}>
                          <AlertTriangle size={11} /> you already logged one this day
                        </span>
                      )}
                      {state.error && (
                        <span className="block text-xs" style={{ color: "var(--status-critical)" }}>
                          {state.error}
                        </span>
                      )}
                    </td>
                    <td className="py-2 text-right">{a.minutes != null ? `${a.minutes} min` : "—"}</td>
                    <td className="py-2 text-right">{a.avg_hr ?? "—"}</td>
                    <td className="py-2 pl-3">
                      {kinds ? (
                        <select
                          value={state.kind}
                          onChange={(e) => setRow(a.activity_id, { kind: e.target.value })}
                          aria-label={`Kind for ${a.label} on ${a.date}`}
                          className={small}
                          style={inputStyle}
                        >
                          {a.maps_to === "running" && <option value="">Not specified</option>}
                          {Object.entries(kinds).map(([k, v]) => (
                            <option key={k} value={k}>
                              {v}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                          Conditioning
                        </span>
                      )}
                    </td>
                    <td className="py-2">
                      <input
                        type="number"
                        min={0}
                        max={10}
                        step="0.5"
                        value={state.rpe}
                        onChange={(e) => setRow(a.activity_id, { rpe: e.target.value })}
                        aria-label={`RPE for ${a.label} on ${a.date}`}
                        className={`${small} w-16`}
                        style={inputStyle}
                      />
                    </td>
                    <td className="py-2">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => add(a)}
                          disabled={state.busy}
                          className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium disabled:opacity-50"
                          style={primaryButton}
                          aria-label={`Add ${a.label} on ${a.date} to my log`}
                        >
                          <Plus size={12} /> Add
                        </button>
                        <button onClick={() => skip(a)} className="text-xs" style={{ color: "var(--text-muted)" }} aria-label={`Skip ${a.label} on ${a.date}`}>
                          Skip
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {strengthHidden > 0 && (
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          {strengthHidden} strength workout{strengthHidden === 1 ? "" : "s"} from your watch aren&rsquo;t listed. Log lifts set by set
          on Workouts (or tell the coach).
        </p>
      )}
    </section>
  );
}
