import { useState } from "react";
import { X } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { AthleticSession, BasketballType, RunType, SessionType } from "../../lib/types";
import { todayLocal } from "../../lib/dates";
import { BASKETBALL_LABELS, formatDuration, formatPace, parseDuration, RUN_TYPE_LABELS, SESSION_LABELS } from "../../lib/running";
import { cardStyle, inputClass, inputStyle, parseNumber, primaryButton, secondaryButton } from "../../lib/ui";

const TYPES: SessionType[] = ["basketball", "running", "sprint", "plyometric", "agility", "conditioning"];

interface Props {
  editing: AthleticSession | null;
  onSaved: (message: string) => void;
  onCancel: () => void;
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
      {label}
      {children}
      {hint && <span style={{ color: "var(--text-muted)" }}>{hint}</span>}
    </label>
  );
}

const str = (v: number | null | undefined) => (v == null ? "" : String(v));

export function LogSessionForm({ editing, onSaved, onCancel }: Props) {
  const [date, setDate] = useState(editing?.session_date ?? todayLocal());
  const [type, setType] = useState<SessionType>(editing?.session_type ?? "running");
  const [runType, setRunType] = useState<RunType | "">(editing?.run_type ?? "");
  const [bballType, setBballType] = useState<BasketballType>(editing?.subtype ?? "practice");
  const [distance, setDistance] = useState(str(editing?.distance_miles));
  const [time, setTime] = useState(editing?.duration_minutes != null ? formatDuration(editing.duration_minutes) : "");
  const [yards, setYards] = useState(str(editing?.sprint_distance_yards));
  const [seconds, setSeconds] = useState(str(editing?.sprint_time_seconds));
  const [jump, setJump] = useState(str(editing?.jump_height_inches));
  const [reps, setReps] = useState(str(editing?.reps));
  const [rpe, setRpe] = useState(str(editing?.rpe));
  const [notes, setNotes] = useState(editing?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const minutes = parseDuration(time);
  const miles = parseNumber(distance);
  const livePace =
    miles && minutes && !Number.isNaN(miles) && !Number.isNaN(minutes) && miles > 0 ? formatPace(minutes / miles) : null;

  const usesDistance = type === "running" || type === "conditioning";
  const usesTime = type === "running" || type === "conditioning" || type === "basketball";
  const rpeNum = parseNumber(rpe);
  const liveLoad =
    minutes && rpeNum != null && !Number.isNaN(minutes) && !Number.isNaN(rpeNum) ? Math.round(minutes * rpeNum) : null;
  const usesSprint = type === "sprint" || type === "agility";

  async function save() {
    const body = {
      session_date: date,
      session_type: type,
      run_type: type === "running" && runType ? runType : null,
      subtype: type === "basketball" ? bballType : null,
      distance_miles: usesDistance ? miles : null,
      duration_minutes: usesTime ? minutes : null,
      sprint_distance_yards: type === "sprint" ? parseNumber(yards) : null,
      sprint_time_seconds: usesSprint ? parseNumber(seconds) : null,
      jump_height_inches: type === "plyometric" ? parseNumber(jump) : null,
      reps: type === "running" || type === "conditioning" || type === "basketball" ? null : parseNumber(reps),
      rpe: parseNumber(rpe),
      notes: notes.trim() || null,
    };

    const numbers = [body.distance_miles, body.duration_minutes, body.sprint_distance_yards, body.sprint_time_seconds, body.jump_height_inches, body.reps, body.rpe];
    if (numbers.some((n) => n != null && Number.isNaN(n))) {
      setError(Number.isNaN(minutes ?? 0) ? "Time should look like 45, 27:30 or 1:05:30." : "Check the numbers — one isn't valid.");
      return;
    }
    if (body.rpe != null && (body.rpe < 0 || body.rpe > 10)) {
      setError("RPE must be between 0 and 10.");
      return;
    }
    if (type === "basketball" && (body.duration_minutes == null || body.rpe == null)) {
      setError("Add minutes and RPE: together they give the session's load.");
      return;
    }
    if (type === "agility" && !body.notes) {
      setError("Name the drill in the notes (e.g. 5-10-5 pro agility).");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (editing) await api.put(`/api/running/sessions/${editing.id}`, body);
      else await api.post("/api/running/sessions", body);
      onSaved(editing ? "Session updated." : `${SESSION_LABELS[type]} saved.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-lg border p-4" style={cardStyle}>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {editing ? "Edit session" : "Log a session"}
        </h2>
        <button onClick={onCancel} aria-label="Close" style={{ color: "var(--text-muted)" }}>
          <X size={16} />
        </button>
      </div>

      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Session type">
        {TYPES.map((t) => (
          <button
            key={t}
            role="radio"
            aria-checked={type === t}
            onClick={() => setType(t)}
            className="rounded-md border px-3 py-1.5 text-sm"
            style={{
              borderColor: type === t ? "var(--series-1)" : "var(--border-hairline)",
              background: type === t ? "var(--surface-2)" : "transparent",
              color: "var(--text-primary)",
            }}
          >
            {SESSION_LABELS[t]}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Field label="Date">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} style={inputStyle} />
        </Field>

        {type === "running" && (
          <Field label="Kind of run">
            <select value={runType} onChange={(e) => setRunType(e.target.value as RunType | "")} className={inputClass} style={inputStyle}>
              <option value="">Not specified</option>
              {Object.entries(RUN_TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
        )}

        {type === "basketball" && (
          <Field label="Kind of session">
            <select value={bballType} onChange={(e) => setBballType(e.target.value as BasketballType)} className={inputClass} style={inputStyle}>
              {Object.entries(BASKETBALL_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </Field>
        )}

        {usesDistance && (
          <Field label={type === "conditioning" ? "Distance (mi, optional)" : "Distance (mi)"}>
            <input type="number" min={0} step="0.01" inputMode="decimal" value={distance} onChange={(e) => setDistance(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
        )}
        {usesTime && (
          <Field
            label={type === "basketball" ? "Minutes on court" : "Time (min, mm:ss or h:mm:ss)"}
            hint={type === "basketball" ? undefined : livePace ? `Pace ${livePace} /mi` : undefined}
          >
            <input value={time} onChange={(e) => setTime(e.target.value)} placeholder="27:30" inputMode="numeric" className={inputClass} style={inputStyle} />
          </Field>
        )}

        {type === "sprint" && (
          <Field label="Distance (yd)">
            <input type="number" min={0} value={yards} onChange={(e) => setYards(e.target.value)} placeholder="40" className={inputClass} style={inputStyle} />
          </Field>
        )}
        {usesSprint && (
          <Field label={type === "sprint" ? "Best time (s)" : "Best drill time (s)"}>
            <input type="number" min={0} step="0.01" inputMode="decimal" value={seconds} onChange={(e) => setSeconds(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
        )}
        {type === "plyometric" && (
          <Field label="Best jump (in, optional)">
            <input type="number" min={0} step="0.5" inputMode="decimal" value={jump} onChange={(e) => setJump(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
        )}
        {(usesSprint || type === "plyometric") && (
          <Field label={type === "plyometric" ? "Reps / contacts" : "Reps"}>
            <input type="number" min={1} step="1" value={reps} onChange={(e) => setReps(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
        )}

        <Field
          label={type === "basketball" ? "RPE (0–10, how hard overall)" : "RPE (0–10)"}
          hint={type === "basketball" && liveLoad != null ? `Load ${liveLoad} (RPE × minutes)` : undefined}
        >
          <input type="number" min={0} max={10} step="0.5" value={rpe} onChange={(e) => setRpe(e.target.value)} className={inputClass} style={inputStyle} />
        </Field>
      </div>

      <Field label={type === "agility" ? "Drill (required) and notes" : "Notes (optional)"}>
        <input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder={
            type === "agility"
              ? "e.g. 5-10-5 pro agility"
              : type === "conditioning"
                ? "e.g. rower 8 x 500m"
                : type === "basketball"
                  ? "e.g. 5v5 scrimmage, lots of sprints; ankle felt fine"
                : type === "plyometric"
                  ? "e.g. box jumps, broad jumps"
                  : ""
          }
          className={inputClass}
          style={inputStyle}
        />
      </Field>

      {error && (
        <p className="text-sm" style={{ color: "var(--status-critical)" }}>
          {error}
        </p>
      )}

      <div className="flex gap-2">
        <button onClick={save} disabled={saving} className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50" style={primaryButton}>
          {saving ? "Saving…" : editing ? "Update" : "Save"}
        </button>
        <button onClick={onCancel} className="rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
          Cancel
        </button>
      </div>
    </section>
  );
}
