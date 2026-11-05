import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Lock, Watch } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { AppSettings, CoachStatus } from "../lib/types";
import { cardStyle, inputClass, inputStyle, primaryButton } from "../lib/ui";
import { GarminSyncWarning } from "../components/garmin/GarminSyncWarning";
import { YourData } from "../components/settings/YourData";

const SYNC_COMMAND = ".venv/bin/python3 garmin_sync.py";

export function Settings() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [status, setStatus] = useState<CoachStatus | null>(null);
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    Promise.all([api.get<AppSettings>("/api/settings"), api.get<CoachStatus>("/api/coach/status")]).then(([s, st]) => {
      setSettings(s);
      setStatus(st);
      setModel(s.ollama_model);
    });
  }, []);

  async function saveModel() {
    setSaving(true);
    setMessage(null);
    try {
      const updated = await api.put<AppSettings>("/api/settings", { ollama_model: model });
      setSettings(updated);
      setMessage({ ok: true, text: `Coach will use ${updated.ollama_model}.` });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof ApiError ? err.message : "Couldn't save." });
    } finally {
      setSaving(false);
    }
  }

  if (!settings || !status) {
    return <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>;
  }

  const options = status.local_models.includes(settings.ollama_model)
    ? status.local_models
    : [settings.ollama_model, ...status.local_models];
  const garmin = status.garmin;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
        Settings / Privacy
      </h1>

      <section className="flex items-start gap-3 rounded-lg border p-4" style={cardStyle}>
        <Lock size={20} style={{ color: "var(--status-good)", flexShrink: 0 }} />
        <div className="flex flex-col gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
          <p className="font-medium" style={{ color: "var(--text-primary)" }}>
            Everything stays on this computer
          </p>
          <ul className="list-disc pl-5">
            <li>This dashboard makes no internet requests — no analytics, telemetry, or cloud sync.</li>
            <li>The AI coach talks only to Ollama at {status.ollama_url}, using a model downloaded to this machine.</li>
            <li>
              Garmin is optional. Its sync script (run by hand, or daily if you turn that on) only downloads your Garmin
              data into its own file, and never sends anything from your logs.
            </li>
          </ul>
        </div>
      </section>

      <YourData />

      <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
        <div>
          <h2 className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            AI coach model
          </h2>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Only models downloaded to this computer are listed. Ollama cloud models aren&rsquo;t allowed.
          </p>
        </div>

        {status.ollama_error ? (
          <p className="flex items-start gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
            <AlertTriangle size={15} style={{ color: "var(--status-warning)", flexShrink: 0, marginTop: 2 }} />
            {status.ollama_error}
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              aria-label="Coach model"
              className={inputClass}
              style={inputStyle}
            >
              {options.map((m) => (
                <option key={m} value={m}>
                  {m}
                  {status.local_models.includes(m) ? "" : " (not downloaded)"}
                </option>
              ))}
            </select>
            <button
              onClick={saveModel}
              disabled={saving || model === settings.ollama_model}
              className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
              style={primaryButton}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        )}
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          To add a model: <code>ollama pull &lt;name&gt;</code> in a terminal, then reload this page.
        </p>
        {message && (
          <p className="flex items-center gap-1.5 text-sm" style={{ color: message.ok ? "var(--text-secondary)" : "var(--status-critical)" }}>
            {message.ok && <CheckCircle2 size={15} style={{ color: "var(--status-good)" }} />}
            {message.text}
          </p>
        )}
      </section>

      <section className="flex items-start gap-3 rounded-lg border p-4" style={cardStyle}>
        <Watch size={20} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
        <div className="flex flex-col gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
          <p className="font-medium" style={{ color: "var(--text-primary)" }}>
            Garmin (optional)
          </p>
          <p>
            Daily sync:{" "}
            {status.garmin_schedule_on ? (
              <strong style={{ color: "var(--text-primary)" }}>on, every day at 8:00 am</strong>
            ) : (
              "off (sync by hand)"
            )}
          </p>
          {!garmin ? (
            <p>Not synced yet. The coach works from your own logs without it.</p>
          ) : (
            <>
              <p>
                Last sync: {garmin.started_at.replace("T", " ").slice(0, 16)} UTC —{" "}
                <span
                  style={{
                    color:
                      garmin.status === "ok"
                        ? "var(--status-good)"
                        : garmin.status === "failed"
                          ? "var(--status-critical)"
                          : "var(--status-warning)",
                  }}
                >
                  {garmin.status}
                </span>{" "}
                ({garmin.range_start} to {garmin.range_end})
              </p>
              {garmin.error && <p style={{ color: "var(--text-muted)" }}>{garmin.error}</p>}
              <p>
                {garmin.fields_mapped
                  ? `Recovery data available for ${garmin.mapped_days} day(s).`
                  : "Data downloaded, but not yet connected to the coach. Run the describe command below and share its output (field names only)."}
              </p>
            </>
          )}
          <GarminSyncWarning status={status} />
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            To sync now, run from the <code>Fitness</code> folder: <code>{SYNC_COMMAND}</code>. Daily sync on/off:{" "}
            <code>scripts/garmin_schedule.sh install</code> / <code>uninstall</code>.
          </p>
        </div>
      </section>
    </div>
  );
}
