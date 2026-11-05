import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, Sparkles, Target } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { AthleteProfile, ChatMessage, CoachStatus, PhaseKey, PhaseOverview, PlanPreview, Sport } from "../lib/types";

const SPORT_LABELS: Record<Sport, string> = { lifting: "Lifting", running: "Running", basketball: "Basketball", other: "Other sport" };
import { formatShortDate } from "../lib/dates";
import { cardStyle, inputClass, inputStyle, primaryButton, secondaryButton } from "../lib/ui";
import { StatCard } from "../components/StatCard";
import { CoachChat } from "../components/coach/CoachChat";

const PHASE_ORDER: PhaseKey[] = ["cut", "maintain", "recomp", "bulk"];
const PHASE_BLURB: Record<PhaseKey, string> = {
  cut: "Lose fat while keeping muscle and strength.",
  maintain: "Hold weight; recover, reset, or focus on performance.",
  recomp: "Hold weight or lose very slowly while building muscle.",
  bulk: "Gain slowly to build muscle and strength.",
};

const CHECK_ICON = {
  good: { Icon: CheckCircle2, color: "var(--status-good)" },
  warn: { Icon: AlertTriangle, color: "var(--status-warning)" },
  unknown: { Icon: CircleHelp, color: "var(--text-muted)" },
};

function Card({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
      {label}
      {children}
    </label>
  );
}

const numOrNull = (raw: string) => (raw.trim() === "" ? null : Number(raw));

export function Goals() {
  const [overview, setOverview] = useState<PhaseOverview | null>(null);
  const [status, setStatus] = useState<CoachStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // profile form
  const [profile, setProfile] = useState<AthleteProfile | null>(null);
  const [heightFt, setHeightFt] = useState("");
  const [heightIn, setHeightIn] = useState("");

  // plan builder
  const [phase, setPhase] = useState<PhaseKey>("cut");
  const [rate, setRate] = useState("");
  const [targetWeight, setTargetWeight] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [days, setDays] = useState("");
  const [priorities, setPriorities] = useState("");
  const [maintenance, setMaintenance] = useState("");
  const [preview, setPreview] = useState<PlanPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // coach recommendation -> seeds the conversation
  const [advice, setAdvice] = useState<ChatMessage[] | null>(null);
  const [asking, setAsking] = useState(false);

  const refresh = useCallback(() => {
    Promise.all([api.get<PhaseOverview>("/api/coach/phase"), api.get<CoachStatus>("/api/coach/status")])
      .then(([o, s]) => {
        setOverview(o);
        setStatus(s);
        setProfile(o.profile);
        if (o.profile.height_in) {
          setHeightFt(String(Math.floor(o.profile.height_in / 12)));
          setHeightIn(String(Math.round(o.profile.height_in % 12)));
        }
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, []);
  useEffect(refresh, [refresh]);

  // Live preview of calories/macros as the builder changes (debounced).
  useEffect(() => {
    if (!overview) return;
    const body = {
      phase,
      weekly_rate_pct: numOrNull(rate),
      target_weight: numOrNull(targetWeight),
      target_date: targetDate || null,
      training_days_per_week: numOrNull(days),
      priorities: priorities || null,
      maintenance_kcal: numOrNull(maintenance),
    };
    const timer = window.setTimeout(() => {
      api
        .post<PlanPreview>("/api/coach/plan/preview", body)
        .then((p) => {
          setPreview(p);
          setPreviewError(null);
        })
        .catch((err: ApiError) => {
          setPreview(null);
          setPreviewError(err.message);
        });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [overview, phase, rate, targetWeight, targetDate, days, priorities, maintenance]);

  async function saveProfile() {
    if (!profile) return;
    const ft = numOrNull(heightFt);
    const inch = numOrNull(heightIn) ?? 0;
    try {
      await api.put("/api/coach/profile", { ...profile, height_in: ft != null ? ft * 12 + inch : null });
      setNotice("Profile saved.");
      refresh();
    } catch (err) {
      setNotice(err instanceof ApiError ? `Couldn't save profile: ${err.message}` : "Couldn't save profile.");
    }
  }

  async function savePlan() {
    setSaving(true);
    try {
      await api.post("/api/coach/plan", {
        phase,
        weekly_rate_pct: numOrNull(rate),
        target_weight: numOrNull(targetWeight),
        target_date: targetDate || null,
        training_days_per_week: numOrNull(days),
        priorities: priorities || null,
        maintenance_kcal: numOrNull(maintenance),
      });
      setNotice("Plan saved. Your daily nutrition targets now match it.");
      refresh();
    } catch (err) {
      setNotice(err instanceof ApiError ? `Couldn't save plan: ${err.message}` : "Couldn't save plan.");
    } finally {
      setSaving(false);
    }
  }

  async function endPlan() {
    if (!window.confirm("End the current plan? Your logs stay; only the plan is archived.")) return;
    await api.delete("/api/coach/plan");
    setNotice("Plan ended.");
    refresh();
  }

  async function askCoach() {
    setAsking(true);
    try {
      const res = await api.post<{ text: string }>("/api/coach/ask", { task: "phase" });
      setAdvice([{ role: "assistant", content: res.text }]);
    } catch (err) {
      setAdvice([{ role: "assistant", content: err instanceof ApiError ? err.message : "The coach didn't respond." }]);
    } finally {
      setAsking(false);
    }
  }

  if (error) {
    return (
      <p className="text-sm" style={{ color: "var(--status-critical)" }}>
        Can&rsquo;t reach the backend: {error}
      </p>
    );
  }
  if (!overview || !status || !profile) {
    return <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>;
  }

  const bal = overview.energy_balance;
  const plan = overview.active_plan;
  const llmReady = status.model_ready && !status.ollama_error;
  const spec = overview.phases[phase];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
          Goals &amp; Phase
        </h1>
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Decide together with the coach whether to cut, bulk, maintain or recomp, then track it against your logs.
        </p>
      </div>

      {notice && (
        <p className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
          <CheckCircle2 size={15} style={{ color: "var(--status-good)" }} /> {notice}
        </p>
      )}

      {/* Where you are now */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Est. maintenance"
          value={bal.maintenance_kcal?.toLocaleString() ?? "—"}
          unit="kcal/day"
          sublabel={bal.maintenance_method ? `${bal.maintenance_method} · ${bal.confidence} confidence` : undefined}
          isEstimate={bal.maintenance_kcal != null}
          isEmpty={bal.maintenance_kcal == null}
          emptyText="Need more logs or a profile"
        />
        <StatCard
          label="Avg intake (28 days)"
          value={bal.avg_intake?.toLocaleString() ?? "—"}
          unit="kcal"
          sublabel={`${bal.days_logged} days logged · ${bal.avg_protein_g ?? "—"} g protein`}
          isEmpty={bal.avg_intake == null}
          emptyText="No meals logged"
        />
        <StatCard
          label="Weight trend"
          value={bal.weekly_change_lb != null ? `${bal.weekly_change_lb > 0 ? "+" : ""}${bal.weekly_change_lb}` : "—"}
          unit="lb/wk"
          sublabel={
            bal.weekly_change_pct != null
              ? `${bal.weekly_change_pct > 0 ? "+" : ""}${bal.weekly_change_pct}% per week · ${bal.weigh_ins} weigh-ins`
              : undefined
          }
          isEmpty={bal.weekly_change_lb == null}
          emptyText={`${bal.weigh_ins} weigh-ins — need 4+ over 10+ days`}
        />
        <StatCard
          label="Body weight"
          value={bal.latest_weight ?? "—"}
          unit="lb"
          sublabel={overview.latest_body_fat != null ? `${overview.latest_body_fat}% body fat` : "body fat not logged"}
          isEmpty={bal.latest_weight == null}
          emptyText="Log on Body Composition"
        />
      </div>
      {bal.notes.map((n) => (
        <p key={n} className="-mt-3 text-xs" style={{ color: "var(--text-muted)" }}>
          {n}
        </p>
      ))}

      {/* Active plan */}
      {plan && (
        <Card
          title={`Current plan — ${overview.phases[plan.phase].label}`}
          action={
            <button onClick={endPlan} className="text-xs" style={{ color: "var(--text-muted)" }}>
              End plan
            </button>
          }
        >
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Since {formatShortDate(plan.start_date)} ({overview.progress?.weeks_in ?? 0} weeks) ·{" "}
            <strong style={{ color: "var(--text-primary)" }}>{Math.round(plan.calorie_target).toLocaleString()} kcal</strong> · P{" "}
            {plan.protein_g} g · C {plan.carbs_g} g · F {plan.fat_g} g · {plan.weekly_rate_pct > 0 ? "+" : ""}
            {plan.weekly_rate_pct}%/week
            {plan.target_weight ? ` · goal ${plan.target_weight} lb` : ""}
            {plan.target_date ? ` by ${formatShortDate(plan.target_date)}` : ""}
          </p>
          {plan.priorities && (
            <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Priorities: {plan.priorities}
            </p>
          )}
          <ul className="flex flex-col gap-1.5 text-sm">
            {overview.progress?.checks.map((c) => {
              const { Icon, color } = CHECK_ICON[c.status];
              return (
                <li key={c.message} className="flex items-start gap-2" style={{ color: "var(--text-secondary)" }}>
                  <Icon size={15} style={{ color, flexShrink: 0, marginTop: 2 }} /> {c.message}
                </li>
              );
            })}
          </ul>
        </Card>
      )}

      {/* Coach recommendation + conversation */}
      <Card
        title="Which phase fits you?"
        action={
          <button
            onClick={askCoach}
            disabled={!llmReady || asking}
            className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm disabled:opacity-50"
            style={secondaryButton}
          >
            <Sparkles size={14} /> {asking ? "Thinking…" : advice ? "Ask again" : "Ask the coach"}
          </button>
        }
      >
        <ul className="list-disc pl-5 text-sm" style={{ color: "var(--text-secondary)" }}>
          {overview.hints.map((h) => (
            <li key={h}>{h}</li>
          ))}
        </ul>
        {!llmReady && (
          <p className="text-xs" style={{ color: "var(--status-warning)" }}>
            The local model isn&rsquo;t available, so only the calculator below works right now.
          </p>
        )}
      </Card>
      {advice && (
        <CoachChat
          key={advice[0].content}
          enabled={llmReady}
          title="Set your goals with the coach"
          placeholderExamples="“I want to bench 225 and see my abs by summer” or “Should I bulk first?”"
          seed={advice}
        />
      )}

      {/* Builder */}
      <Card title={plan ? "Plan a new phase" : "Plan your phase"}>
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4" role="radiogroup" aria-label="Phase">
          {PHASE_ORDER.map((key) => (
            <button
              key={key}
              role="radio"
              aria-checked={phase === key}
              onClick={() => {
                setPhase(key);
                setRate("");
              }}
              className="flex flex-col gap-0.5 rounded-md border p-3 text-left"
              style={{
                borderColor: phase === key ? "var(--series-1)" : "var(--border-hairline)",
                background: phase === key ? "var(--surface-2)" : "transparent",
              }}
            >
              <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                {overview.phases[key].label}
              </span>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                {PHASE_BLURB[key]}
              </span>
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
          <Field label={`Rate (% body weight / week; usual ${spec.rate_range[0]} to ${spec.rate_range[1]})`}>
            <input type="number" step="0.05" value={rate} placeholder={String(spec.default_rate)} onChange={(e) => setRate(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
          <Field label="Goal weight (lb, optional)">
            <input type="number" step="0.5" value={targetWeight} onChange={(e) => setTargetWeight(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
          <Field label="Goal date (optional)">
            <input type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
          <Field label="Training days / week">
            <input type="number" min={1} max={7} value={days} onChange={(e) => setDays(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
          <Field label={`Maintenance kcal (leave blank to use ${bal.maintenance_kcal?.toLocaleString() ?? "estimate"})`}>
            <input type="number" step="10" value={maintenance} onChange={(e) => setMaintenance(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
          <Field label="Priorities (what matters most)">
            <input value={priorities} placeholder="e.g. bench 225, keep squat, visible abs" onChange={(e) => setPriorities(e.target.value)} className={inputClass} style={inputStyle} />
          </Field>
        </div>

        {previewError && (
          <p className="text-sm" style={{ color: "var(--status-warning)" }}>
            {previewError}
          </p>
        )}
        {preview && (
          <div className="flex flex-col gap-2 rounded-md p-3" style={{ background: "var(--surface-2)" }}>
            <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm tabular-nums" style={{ color: "var(--text-secondary)" }}>
              <span>
                <Target size={14} className="mr-1 inline" />
                <strong className="text-lg" style={{ color: "var(--text-primary)" }}>
                  {preview.calorie_target.toLocaleString()}
                </strong>{" "}
                kcal/day ({preview.daily_energy_delta > 0 ? "+" : ""}
                {preview.daily_energy_delta} vs. maintenance)
              </span>
              <span>Protein {preview.protein_g} g</span>
              <span>Carbs {preview.carbs_g} g</span>
              <span>Fat {preview.fat_g} g</span>
              <span>
                {preview.weekly_change_lb > 0 ? "+" : ""}
                {preview.weekly_change_lb} lb/week
              </span>
              {preview.weeks_to_target && <span>~{preview.weeks_to_target} weeks to goal</span>}
            </p>
            {preview.warnings.map((w) => (
              <p key={w} className="flex items-center gap-1.5 text-xs" style={{ color: "var(--status-warning)" }}>
                <AlertTriangle size={13} /> {w}
              </p>
            ))}
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              Based on {preview.start_weight} lb and {preview.maintenance_kcal.toLocaleString()} kcal maintenance. Saving sets your
              daily Nutrition targets to these numbers.
            </p>
          </div>
        )}
        <div>
          <button onClick={savePlan} disabled={!preview || saving} className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50" style={primaryButton}>
            {saving ? "Saving…" : plan ? "Replace current plan" : "Start this plan"}
          </button>
        </div>
      </Card>

      {/* Profile */}
      <Card title="Your profile (improves estimates)">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Field label="Sex">
            <select
              value={profile.sex ?? ""}
              onChange={(e) => setProfile({ ...profile, sex: (e.target.value || null) as AthleteProfile["sex"] })}
              className={inputClass}
              style={inputStyle}
            >
              <option value="">Prefer not to say</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </Field>
          <Field label="Birth year">
            <input type="number" value={profile.birth_year ?? ""} onChange={(e) => setProfile({ ...profile, birth_year: numOrNull(e.target.value) })} className={inputClass} style={inputStyle} />
          </Field>
          <Field label="Height (ft / in)">
            <div className="flex gap-1">
              <input type="number" value={heightFt} onChange={(e) => setHeightFt(e.target.value)} aria-label="Feet" className={`${inputClass} w-full`} style={inputStyle} />
              <input type="number" value={heightIn} onChange={(e) => setHeightIn(e.target.value)} aria-label="Inches" className={`${inputClass} w-full`} style={inputStyle} />
            </div>
          </Field>
          <Field label="Lifting experience">
            <select
              value={profile.experience ?? ""}
              onChange={(e) => setProfile({ ...profile, experience: (e.target.value || null) as AthleteProfile["experience"] })}
              className={inputClass}
              style={inputStyle}
            >
              <option value="">—</option>
              <option value="beginner">Beginner (&lt; 1 year)</option>
              <option value="intermediate">Intermediate (1–4 years)</option>
              <option value="advanced">Advanced (4+ years)</option>
            </select>
          </Field>
        </div>
        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1 text-xs" style={{ color: "var(--text-muted)" }}>
            What you train (the coach and planner adapt to this)
            {profile.sports === null && profile.effective_sports.length > 0 && " — guessed from your logs until you save"}
          </legend>
          <div className="flex flex-wrap gap-3">
            {(Object.keys(SPORT_LABELS) as Sport[]).map((sport) => {
              const current = profile.sports ?? profile.effective_sports;
              return (
                <label key={sport} className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
                  <input
                    type="checkbox"
                    checked={current.includes(sport)}
                    onChange={(e) =>
                      setProfile({
                        ...profile,
                        sports: e.target.checked ? [...current, sport] : current.filter((s) => s !== sport),
                      })
                    }
                  />
                  {SPORT_LABELS[sport]}
                </label>
              );
            })}
          </div>
        </fieldset>
        <div>
          <button onClick={saveProfile} className="rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
            Save profile
          </button>
        </div>
      </Card>
    </div>
  );
}
