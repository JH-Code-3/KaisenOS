import { useState } from "react";
import { ApiError } from "../../lib/api";
import { formatShortDate } from "../../lib/dates";
import { cardStyle, inputClass, inputStyle, parseNumber, primaryButton } from "../../lib/ui";

export interface CheckInField<K extends string> {
  key: K;
  label: string;
  min: number;
  max?: number;
  step: string;
  placeholder?: string;
}

type Values<K extends string> = Record<K, number | null>;

interface Props<K extends string> {
  title: string;
  fields: CheckInField<K>[];
  date: string;
  onDateChange: (date: string) => void;
  /** The entry already saved for `date`, if any. Saving then updates it. */
  existing: (Values<K> & { notes: string | null }) | null;
  requireOneMessage: string;
  onSave: (values: Values<K>, notes: string | null) => Promise<void>;
}

/**
 * One-row daily check-in (recovery, body). Picking a date that already
 * has an entry loads it for editing instead of creating a duplicate.
 */
export function CheckInForm<K extends string>(props: Props<K>) {
  // Remount whenever the date or loaded entry changes so fields reset.
  const resetKey = `${props.date}:${JSON.stringify(props.existing)}`;
  return <CheckInFormInner key={resetKey} {...props} />;
}

function CheckInFormInner<K extends string>({
  title,
  fields,
  date,
  onDateChange,
  existing,
  requireOneMessage,
  onSave,
}: Props<K>) {
  const [raw, setRaw] = useState<Record<K, string>>(
    () => Object.fromEntries(fields.map((f) => [f.key, existing?.[f.key]?.toString() ?? ""])) as Record<K, string>,
  );
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit() {
    const values = {} as Values<K>;
    const problems: string[] = [];

    for (const f of fields) {
      const v = parseNumber(raw[f.key]);
      if (v != null && (Number.isNaN(v) || v < f.min || (f.max != null && v > f.max))) {
        const name = f.label.replace(/\s*\(.*\)$/, "");
        problems.push(f.max != null ? `${name} must be between ${f.min} and ${f.max}.` : `${name} can't be below ${f.min}.`);
      }
      values[f.key] = v;
    }
    if (Object.values(values).every((v) => v == null)) problems.push(requireOneMessage);
    if (!date) problems.push("Pick a date.");

    if (problems.length) {
      setError(problems.join(" "));
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await onSave(values, notes.trim() || null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {title}
        </h2>
        {existing && (
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Editing your entry for {formatShortDate(date)}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-[10rem_repeat(auto-fit,minmax(7rem,1fr))]">
        <label className="col-span-2 flex flex-col gap-1 text-xs sm:col-span-1" style={{ color: "var(--text-muted)" }}>
          Date
          <input
            type="date"
            value={date}
            onChange={(e) => e.target.value && onDateChange(e.target.value)}
            className={inputClass}
            style={inputStyle}
          />
        </label>
        {fields.map((f) => (
          <label key={f.key} className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
            {f.label}
            <input
              type="number"
              min={f.min}
              max={f.max}
              step={f.step}
              inputMode="decimal"
              placeholder={f.placeholder}
              value={raw[f.key]}
              onChange={(e) => setRaw((r) => ({ ...r, [f.key]: e.target.value }))}
              className={inputClass}
              style={inputStyle}
            />
          </label>
        ))}
      </div>

      <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
        Notes (optional)
        <input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className={inputClass}
          style={inputStyle}
        />
      </label>

      {error && (
        <p className="text-sm" style={{ color: "var(--status-critical)" }}>
          {error}
        </p>
      )}

      <div>
        <button
          onClick={submit}
          disabled={saving}
          className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          style={primaryButton}
        >
          {saving ? "Saving…" : existing ? "Update" : "Save"}
        </button>
      </div>
    </section>
  );
}
