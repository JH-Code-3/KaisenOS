import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import type { NutritionTarget } from "../../lib/types";
import { formatShortDate } from "../../lib/dates";
import { cardStyle, inputClass, inputStyle, parseNumber, primaryButton, secondaryButton } from "../../lib/ui";

const FIELDS = [
  ["calories", "Calories (kcal)"],
  ["protein_g", "Protein (g)"],
  ["carbs_g", "Carbs (g)"],
  ["fat_g", "Fat (g)"],
] as const;

type Field = (typeof FIELDS)[number][0];

interface Props {
  effectiveDate: string;
  current: NutritionTarget | null;
  onSaved: () => void;
  onCancel: () => void;
}

/**
 * Daily targets apply from `effectiveDate` onward; earlier days keep
 * whatever target was in effect then.
 */
export function TargetsForm({ effectiveDate, current, onSaved, onCancel }: Props) {
  const [values, setValues] = useState<Record<Field, string>>(() => ({
    calories: current?.calories?.toString() ?? "",
    protein_g: current?.protein_g?.toString() ?? "",
    carbs_g: current?.carbs_g?.toString() ?? "",
    fat_g: current?.fat_g?.toString() ?? "",
  }));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    const parsed = Object.fromEntries(FIELDS.map(([key]) => [key, parseNumber(values[key])])) as Record<
      Field,
      number | null
    >;

    if (Object.values(parsed).every((v) => v == null)) {
      setError("Enter at least one target.");
      return;
    }
    if (Object.values(parsed).some((v) => v != null && (Number.isNaN(v) || v < 0))) {
      setError("Targets must be positive numbers.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await api.post("/api/nutrition/targets", { effective_date: effectiveDate, ...parsed });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
      <div>
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Daily targets
        </h2>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Applies from {formatShortDate(effectiveDate)} onward. Leave a field blank to not track it.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {FIELDS.map(([key, label]) => (
          <label key={key} className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
            {label}
            <input
              type="number"
              min={0}
              inputMode="decimal"
              value={values[key]}
              onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
              className={inputClass}
              style={inputStyle}
            />
          </label>
        ))}
      </div>

      {error && (
        <p className="text-sm" style={{ color: "var(--status-critical)" }}>
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          style={primaryButton}
        >
          {saving ? "Saving…" : "Save targets"}
        </button>
        <button onClick={onCancel} className="rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
          Cancel
        </button>
      </div>
    </section>
  );
}
