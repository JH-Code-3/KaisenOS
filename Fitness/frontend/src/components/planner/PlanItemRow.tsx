import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { PlanItem } from "../../lib/types";
import { formatShortDate } from "../../lib/dates";
import { inputClass, inputStyle, parseNumber, primaryButton, secondaryButton } from "../../lib/ui";

interface Props {
  item: PlanItem;
  weekDates: string[];
  onChanged: () => void;
}

const small = `${inputClass} w-full min-w-0 px-1.5 py-1 text-xs`;

export function PlanItemRow({ item, weekDates, onChanged }: Props) {
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    item_date: item.item_date,
    exercise: item.exercise ?? "",
    prescribed_weight: item.prescribed_weight?.toString() ?? "",
    sets: item.sets?.toString() ?? "",
    reps: item.reps?.toString() ?? "",
    planned_work: item.planned_work ?? "",
  });

  async function patch(body: Record<string, unknown>) {
    setError(null);
    try {
      await api.patch(`/api/planner/items/${item.id}`, body);
      onChanged();
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save.");
      return false;
    }
  }

  async function saveEdit() {
    const body: Record<string, unknown> = { item_date: form.item_date };
    if (item.category === "strength") {
      Object.assign(body, {
        exercise: form.exercise.trim() || undefined,
        prescribed_weight: parseNumber(form.prescribed_weight),
        sets: parseNumber(form.sets) ?? undefined,
        reps: parseNumber(form.reps) ?? undefined,
      });
    } else {
      body.planned_work = form.planned_work.trim() || undefined;
    }
    if (await patch(body)) setEditing(false);
  }

  async function remove() {
    if (!window.confirm("Remove this from the plan?")) return;
    try {
      await api.delete(`/api/planner/items/${item.id}`);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't remove.");
    }
  }

  const label =
    item.category === "strength"
      ? item.exercise
      : item.category === "basketball"
        ? `Basketball ${item.session_type?.toLowerCase()}`
        : `${item.session_type} run`;
  const detail =
    item.category === "strength"
      ? `${item.sets} × ${item.reps}${item.prescribed_weight != null ? ` @ ${item.prescribed_weight} lb` : ""}${item.target_rpe ? ` · RPE ${item.target_rpe}` : ""}`
      : [item.planned_work, item.target].filter(Boolean).join(" · ");

  return (
    <li className="flex flex-col gap-1.5 border-t py-2" style={{ borderColor: "var(--border-hairline)" }}>
      <div className="flex items-start gap-2">
        <input
          type="checkbox"
          checked={item.done}
          disabled={item.auto_completed}
          onChange={(e) => patch({ is_completed: e.target.checked })}
          aria-label={`Mark ${label} done`}
          title={item.auto_completed ? "Done: found in your log" : undefined}
          className="mt-0.5 h-4 w-4 shrink-0"
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm" style={{ color: "var(--text-primary)", textDecoration: item.done ? "line-through" : undefined, opacity: item.done ? 0.7 : 1 }}>
            {label}
            {item.auto_completed && (
              <span className="ml-1.5 rounded px-1 py-0.5 text-[10px] font-medium uppercase" style={{ background: "var(--surface-2)", color: "var(--text-muted)" }}>
                logged
              </span>
            )}
          </p>
          <p className="text-xs tabular-nums" style={{ color: "var(--text-secondary)" }} title={item.notes ?? undefined}>
            {detail}
          </p>
          {item.notes && !item.done && (
            <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
              {item.notes}
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2" style={{ color: "var(--text-muted)" }}>
          <button onClick={() => setEditing((v) => !v)} aria-label={`Edit ${label}`} title="Edit or move">
            <Pencil size={13} />
          </button>
          <button onClick={remove} aria-label={`Remove ${label}`} title="Remove">
            <Trash2 size={13} />
          </button>
        </div>
      </div>

      {editing && (
        <div className="flex flex-col gap-2 rounded-md p-2" style={{ background: "var(--surface-2)" }}>
          <div className="grid grid-cols-2 gap-1.5 text-[11px]" style={{ color: "var(--text-muted)" }}>
            <label className="col-span-2 flex flex-col gap-0.5">
              Day
              <select value={form.item_date} onChange={(e) => setForm({ ...form, item_date: e.target.value })} className={small} style={inputStyle}>
                {weekDates.map((d) => (
                  <option key={d} value={d}>
                    {formatShortDate(d)}
                  </option>
                ))}
              </select>
            </label>
            {item.category === "strength" ? (
              <>
                <label className="col-span-2 flex flex-col gap-0.5">
                  Exercise
                  <input value={form.exercise} onChange={(e) => setForm({ ...form, exercise: e.target.value })} className={small} style={inputStyle} />
                </label>
                <label className="flex flex-col gap-0.5">
                  Weight (lb)
                  <input type="number" min={0} value={form.prescribed_weight} onChange={(e) => setForm({ ...form, prescribed_weight: e.target.value })} className={small} style={inputStyle} />
                </label>
                <div className="grid grid-cols-2 gap-1.5">
                  <label className="flex flex-col gap-0.5">
                    Sets
                    <input type="number" min={1} value={form.sets} onChange={(e) => setForm({ ...form, sets: e.target.value })} className={small} style={inputStyle} />
                  </label>
                  <label className="flex flex-col gap-0.5">
                    Reps
                    <input type="number" min={1} value={form.reps} onChange={(e) => setForm({ ...form, reps: e.target.value })} className={small} style={inputStyle} />
                  </label>
                </div>
              </>
            ) : (
              <label className="col-span-2 flex flex-col gap-0.5">
                Planned
                <input value={form.planned_work} onChange={(e) => setForm({ ...form, planned_work: e.target.value })} className={small} style={inputStyle} />
              </label>
            )}
          </div>
          <div className="flex gap-1.5">
            <button onClick={saveEdit} className="rounded px-2 py-1 text-xs font-medium" style={primaryButton}>
              Save
            </button>
            <button onClick={() => setEditing(false)} className="rounded px-2 py-1 text-xs" style={secondaryButton}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {error && (
        <p className="text-xs" style={{ color: "var(--status-critical)" }}>
          {error}
        </p>
      )}
    </li>
  );
}
