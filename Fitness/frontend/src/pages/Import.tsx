import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Lock, Undo2 } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { ImportBatch, ImportDay, ImportJob } from "../lib/types";
import { cardStyle, inputClass, inputStyle, primaryButton, secondaryButton } from "../lib/ui";
import { ImportDayCard } from "../components/import/ImportDayCard";
import { buildCommit } from "../lib/importCommit";

type Stage = "paste" | "reading" | "review" | "saved";

const MAX_CHARS = 150_000;

// Only the job id is remembered (never the notes), and only for this browser tab.
const JOB_KEY = "kaisen-import-job";
function rememberJob(id: string | null) {
  try {
    if (id) sessionStorage.setItem(JOB_KEY, id);
    else sessionStorage.removeItem(JOB_KEY);
  } catch {
    // storage unavailable: resuming just won't work
  }
}
function recallJob(): string | null {
  try {
    return sessionStorage.getItem(JOB_KEY);
  } catch {
    return null;
  }
}

export function Import() {
  const [stage, setStage] = useState<Stage>(() => (recallJob() ? "reading" : "paste"));
  const [text, setText] = useState("");
  const [job, setJob] = useState<ImportJob | null>(() =>
    recallJob() ? { status: "running", done: 0, total: 0, days: null, error: null } : null,
  );
  const [days, setDays] = useState<ImportDay[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<{ batch_id: number; days: number; meals: number; workout_sessions: number } | null>(null);
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const poll = useRef<number | null>(null);

  const loadBatches = useCallback(() => {
    api.get<ImportBatch[]>("/api/import/batches").then(setBatches).catch(() => setBatches([]));
  }, []);
  useEffect(loadBatches, [loadBatches]);

  const watchJob = useCallback((jobId: string) => {
    if (poll.current) window.clearInterval(poll.current);
    const stop = () => {
      window.clearInterval(poll.current!);
      rememberJob(null);
    };
    poll.current = window.setInterval(async () => {
      try {
        const j = await api.get<ImportJob>(`/api/import/jobs/${jobId}`);
        setJob(j);
        if (j.status !== "running") {
          stop();
          if (j.status === "done") {
            setDays(j.days ?? []);
            setStage("review");
          } else {
            setError(j.error ?? "Import failed.");
            setStage("paste");
          }
        }
      } catch (err) {
        stop();
        setError(err instanceof ApiError ? err.message : "Lost track of the import.");
        setStage("paste");
      }
    }, 1500);
  }, []);

  // Pick a running import back up if you left the page and came back.
  useEffect(() => {
    const pending = recallJob();
    if (pending) watchJob(pending);
    return () => {
      if (poll.current) window.clearInterval(poll.current);
    };
  }, [watchJob]);

  async function startReading() {
    setError(null);
    try {
      const { job_id } = await api.post<{ job_id: string }>("/api/import/parse", { text });
      rememberJob(job_id);
      setStage("reading");
      setJob({ status: "running", done: 0, total: 0, days: null, error: null });
      watchJob(job_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start reading the notes.");
    }
  }

  async function save() {
    const { days: payload, errors: problems } = buildCommit(days);
    setErrors(problems);
    if (problems.length) return;
    setSaving(true);
    try {
      const res = await api.post<typeof saved & object>("/api/import/commit", { days: payload });
      setSaved(res);
      setStage("saved");
      loadBatches();
    } catch (err) {
      setErrors([err instanceof ApiError ? err.message : "Save failed."]);
    } finally {
      setSaving(false);
    }
  }

  async function undo(batchId: number) {
    if (!window.confirm("Remove everything this import added? This can't be undone.")) return;
    await api.post(`/api/import/batches/${batchId}/undo`, {});
    loadBatches();
    if (saved?.batch_id === batchId) {
      setSaved(null);
      setStage("review");
    }
  }

  const included = days.filter((d) => d.include);
  const stats = {
    days: included.length,
    meals: included.reduce((s, d) => s + (d.include_meals ? d.meals.length : 0), 0),
    workouts: included.reduce((s, d) => s + (d.include_workouts ? d.workouts.length : 0), 0),
    activities: included.reduce((s, d) => s + (d.include_activities ? (d.activities?.length ?? 0) : 0), 0),
    estimates: included.reduce((s, d) => s + d.meals.flatMap((m) => m.items).filter((i) => i.is_estimate).length, 0),
    notImported: days.reduce((s, d) => s + d.not_imported.length, 0),
    noDate: included.filter((d) => !d.date).length,
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Import Notes
        </h1>
        <p className="flex flex-wrap items-center gap-1.5 text-sm" style={{ color: "var(--text-muted)" }}>
          <Lock size={13} /> Paste your meal and workout notes. Your local model reads them on this computer, you check
          the result, and nothing is saved until you confirm.
        </p>
      </div>

      {error && (
        <p className="text-sm" style={{ color: "var(--status-critical)" }}>
          {error}
        </p>
      )}

      {stage === "paste" && (
        <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={16}
            maxLength={MAX_CHARS}
            placeholder={"Paste your notes here, any format. For example:\n\nOct 27\nbreakfast 3 eggs, toast\nbench 155x5x3 @8, ohp 95 3x8\nbw 201.4\n\n10/28 rest day, slept 6.5h, legs sore"}
            aria-label="Notes to import"
            className={`${inputClass} font-mono text-xs leading-relaxed`}
            style={inputStyle}
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Starting each day with a date (&ldquo;Oct 27&rdquo;, &ldquo;10/27&rdquo;) gives the best results. Takes about
              20–30 seconds per day. {text.length.toLocaleString()} / {MAX_CHARS.toLocaleString()} characters.
            </p>
            <button
              onClick={startReading}
              disabled={!text.trim()}
              className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
              style={primaryButton}
            >
              Read my notes
            </button>
          </div>
        </section>
      )}

      {stage === "reading" && job && (
        <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle} aria-live="polite">
          <p className="text-sm" style={{ color: "var(--text-primary)" }}>
            Reading your notes&hellip; {job.total ? `day ${Math.min(job.done + 1, job.total)} of ${job.total}` : ""}
          </p>
          <div
            className="h-2 overflow-hidden rounded-full"
            style={{ background: "var(--surface-2)" }}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={job.total || 1}
            aria-valuenow={job.done}
          >
            <div className="h-full rounded-full transition-all" style={{ width: `${job.total ? (job.done / job.total) * 100 : 3}%`, background: "var(--series-1)" }} />
          </div>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            It keeps going if you switch pages; come back here to review.
          </p>
        </section>
      )}

      {stage === "review" && (
        <>
          <section className="flex flex-col gap-2 rounded-lg border p-4 text-sm" style={cardStyle}>
            <p style={{ color: "var(--text-primary)" }}>
              Found <strong>{stats.days}</strong> days: <strong>{stats.meals}</strong> meals and{" "}
              <strong>{stats.workouts}</strong> workouts, <strong>{stats.activities}</strong> runs/basketball/conditioning.
            </p>
            <ul className="list-disc pl-5 text-xs" style={{ color: "var(--text-secondary)" }}>
              {stats.estimates > 0 && (
                <li>{stats.estimates} foods had no calories in your notes, so they&rsquo;re estimated (marked EST). Fix any you know.</li>
              )}
              {stats.notImported > 0 && <li>{stats.notImported} lines weren&rsquo;t imported. They&rsquo;re shown in orange on their day.</li>}
              {stats.noDate > 0 && <li>{stats.noDate} day(s) need a date.</li>}
              <li>Hover a row to see the note it came from. Untick anything you don&rsquo;t want saved.</li>
            </ul>
          </section>

          {days.map((d, i) => (
            <ImportDayCard key={i} day={d} index={i} onChange={(nd) => setDays((all) => all.map((x, j) => (j === i ? nd : x)))} />
          ))}

          {errors.length > 0 && (
            <ul className="list-disc pl-5 text-sm" style={{ color: "var(--status-critical)" }}>
              {errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}

          <div className="flex gap-2">
            <button onClick={save} disabled={saving} className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50" style={primaryButton}>
              {saving ? "Saving…" : `Save ${stats.days} day${stats.days === 1 ? "" : "s"}`}
            </button>
            <button
              onClick={() => {
                setStage("paste");
                setDays([]);
                setErrors([]);
              }}
              className="rounded-md px-3 py-1.5 text-sm"
              style={secondaryButton}
            >
              Start over
            </button>
          </div>
        </>
      )}

      {stage === "saved" && saved && (
        <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
          <p className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-primary)" }}>
            <CheckCircle2 size={16} style={{ color: "var(--status-good)" }} /> Saved {saved.days} days: {saved.meals} meals and{" "}
            {saved.workout_sessions} workouts.
          </p>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            They now show on the Nutrition, Workouts, Recovery and Body pages, and the AI Coach uses them.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => {
                setStage("paste");
                setText("");
                setDays([]);
              }}
              className="rounded-md px-3 py-1.5 text-sm"
              style={secondaryButton}
            >
              Import more
            </button>
            <button onClick={() => undo(saved.batch_id)} className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
              <Undo2 size={14} /> Undo this import
            </button>
          </div>
        </section>
      )}

      {batches.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Past imports
          </h2>
          <ul className="flex flex-col gap-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            {batches.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center gap-3 rounded-md border px-3 py-2" style={cardStyle}>
                <span>{new Date(`${b.created_at.replace(" ", "T")}Z`).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</span>
                <span style={{ color: "var(--text-muted)" }}>
                  {b.days} days · {b.meals} meals · {b.workout_sessions} workouts
                </span>
                {b.undone_at ? (
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    undone
                  </span>
                ) : (
                  <button onClick={() => undo(b.id)} className="ml-auto flex items-center gap-1 text-xs" style={{ color: "var(--series-1)" }}>
                    <Undo2 size={13} /> Undo
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
