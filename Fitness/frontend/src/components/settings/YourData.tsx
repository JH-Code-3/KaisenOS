import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Archive, CheckCircle2, Download, HardDrive, RotateCcw, Trash2 } from "lucide-react";
import { api, API_BASE, ApiError } from "../../lib/api";
import { cardStyle, inputClass, inputStyle, primaryButton, secondaryButton } from "../../lib/ui";

interface Summary {
  data_dir: string;
  total_size_bytes: number;
  counts: Record<string, number>;
  has_garmin: boolean;
  backups: number;
  keep_backups: number;
}

interface Backup {
  name: string;
  created: string;
  reason: string;
  size_bytes: number;
  has_garmin: boolean;
}

const mb = (bytes: number) => `${(bytes / 1_048_576).toFixed(bytes < 1_048_576 ? 2 : 1)} MB`;
const REASONS: Record<string, string> = { auto: "Automatic", manual: "Manual", "pre-restore": "Before a restore" };

/** Where your data lives, backups, export and delete. Everything stays on this computer. */
export function YourData() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [backups, setBackups] = useState<Backup[]>([]);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [includeBackups, setIncludeBackups] = useState(false);

  const load = useCallback(() => {
    api.get<Summary>("/api/data/summary").then(setSummary).catch(() => setSummary(null));
    api.get<Backup[]>("/api/data/backups").then(setBackups).catch(() => setBackups([]));
  }, []);
  useEffect(load, [load]);

  async function run(action: () => Promise<string>) {
    setBusy(true);
    setMessage(null);
    try {
      setMessage({ ok: true, text: await action() });
      load();
    } catch (err) {
      setMessage({ ok: false, text: err instanceof ApiError ? err.message : "Something went wrong." });
    } finally {
      setBusy(false);
    }
  }

  const backupNow = () =>
    run(async () => {
      await api.post("/api/data/backups", {});
      return "Backup created.";
    });

  const restore = (b: Backup) => {
    if (!window.confirm(`Replace your current data with the backup from ${new Date(b.created).toLocaleString()}? Your current data is backed up first.`))
      return;
    run(async () => {
      const r = await api.post<{ safety_backup: string }>(`/api/data/backups/${b.name}/restore`, {});
      return `Restored. Your previous data was saved as a backup first (${r.safety_backup}). Reload the page to see it.`;
    });
  };

  const deleteAll = () =>
    run(async () => {
      await api.post("/api/data/delete", { confirm: confirmText, include_backups: includeBackups });
      setConfirmText("");
      return includeBackups ? "All app data and backups deleted." : "All app data deleted. Backups were kept.";
    });

  if (!summary) return null;
  const total = Object.values(summary.counts).reduce((a, b) => a + b, 0);

  return (
    <section className="flex flex-col gap-4 rounded-lg border p-4" style={cardStyle}>
      <div className="flex items-start gap-3">
        <HardDrive size={20} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
        <div className="flex min-w-0 flex-col gap-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          <p className="font-medium" style={{ color: "var(--text-primary)" }}>
            Your data
          </p>
          <p>
            Stored only on this computer, in a folder only your account can open ({mb(summary.total_size_bytes)}, {total.toLocaleString()} entries):
          </p>
          <code className="break-all text-xs" style={{ color: "var(--text-muted)" }}>
            {summary.data_dir}
          </code>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Not encrypted by the app. Turn on FileVault (Mac), BitLocker (Windows) or disk encryption (Linux) to protect it if your computer is lost.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <a href={`${API_BASE}/api/data/export.json`} className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
          <Download size={14} /> Export everything (JSON)
        </a>
        <a href={`${API_BASE}/api/data/export.zip`} className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
          <Download size={14} /> Export as spreadsheets (CSV zip)
        </a>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            Backups
          </p>
          <button onClick={backupNow} disabled={busy} className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm disabled:opacity-50" style={secondaryButton}>
            <Archive size={14} /> Back up now
          </button>
        </div>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          A backup is made automatically once a day when the app starts, and before any restore. The newest {summary.keep_backups} are kept; older
          ones are deleted. Backups are in the same private folder and aren&rsquo;t encrypted either.
        </p>
        {backups.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            No backups yet.
          </p>
        ) : (
          <ul className="flex flex-col">
            {backups.map((b) => (
              <li key={b.name} className="flex flex-wrap items-center gap-3 border-t py-1.5 text-sm" style={{ borderColor: "var(--border-hairline)", color: "var(--text-secondary)" }}>
                <span className="tabular-nums">{new Date(b.created).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}</span>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {REASONS[b.reason] ?? b.reason} · {mb(b.size_bytes)}
                  {b.has_garmin ? " · incl. Garmin" : ""}
                </span>
                <button onClick={() => restore(b)} disabled={busy} className="ml-auto flex items-center gap-1 text-xs disabled:opacity-50" style={{ color: "var(--series-1)" }}>
                  <RotateCcw size={12} /> Restore
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-col gap-2 rounded-md border p-3" style={{ borderColor: "var(--status-critical)" }}>
        <p className="flex items-center gap-1.5 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          <AlertTriangle size={14} style={{ color: "var(--status-critical)" }} /> Delete all my data
        </p>
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Removes your training log, Garmin data, settings, exports and sync log from this computer and starts fresh. Export first if you want a
          copy. This can&rsquo;t remove copies you made yourself (downloaded exports, Time Machine), and it doesn&rsquo;t delete anything from your
          Garmin account or your Garmin key in the <code>.env</code> file.
        </p>
        <label className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
          <input type="checkbox" checked={includeBackups} onChange={(e) => setIncludeBackups(e.target.checked)} />
          Also delete all {summary.backups} backup{summary.backups === 1 ? "" : "s"}
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="Type DELETE"
            aria-label="Type DELETE to confirm"
            className={`${inputClass} w-36`}
            style={inputStyle}
          />
          <button
            onClick={deleteAll}
            disabled={busy || confirmText !== "DELETE"}
            className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-40"
            style={{ ...primaryButton, background: "var(--status-critical)" }}
          >
            <Trash2 size={14} /> Delete everything
          </button>
        </div>
      </div>

      {message && (
        <p className="flex items-center gap-1.5 text-sm" style={{ color: message.ok ? "var(--text-secondary)" : "var(--status-critical)" }}>
          {message.ok && <CheckCircle2 size={15} style={{ color: "var(--status-good)" }} />}
          {message.text}
        </p>
      )}
    </section>
  );
}
