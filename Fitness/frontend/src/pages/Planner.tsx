import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CalendarRange, ChevronLeft, ChevronRight, Download, RefreshCw } from "lucide-react";
import { api, API_BASE, ApiError } from "../lib/api";
import type { DayStatus, PlanWeek } from "../lib/types";
import { formatShortDate, shiftDate, todayLocal } from "../lib/dates";
import { cardStyle, inputClass, inputStyle, primaryButton, secondaryButton } from "../lib/ui";
import { PlanItemRow } from "../components/planner/PlanItemRow";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function mondayOf(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const weekday = (new Date(y, m - 1, d).getDay() + 6) % 7; // Mon = 0
  return shiftDate(iso, -weekday);
}

const STATUS_OPTIONS: { value: DayStatus; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "practice", label: "Practice" },
  { value: "game", label: "Game" },
  { value: "busy", label: "Busy" },
];

/** Per day: what's happening (open/busy/basketball) and whether you lift. */
function WeekSetup({
  statuses,
  liftDays,
  onStatuses,
  onLiftDays,
}: {
  statuses: DayStatus[];
  liftDays: number[];
  onStatuses: (s: DayStatus[]) => void;
  onLiftDays: (d: number[]) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
      {DAY_NAMES.map((name, i) => {
        const canLift = statuses[i] === "open" || statuses[i] === "practice";
        const lifting = canLift && liftDays.includes(i);
        return (
          <div key={name} className="flex flex-col gap-1.5 rounded-md border p-2" style={{ borderColor: "var(--border-hairline)" }}>
            <span className="text-xs font-medium" style={{ color: "var(--text-primary)" }}>
              {name}
            </span>
            <select
              value={statuses[i]}
              onChange={(e) => {
                const next = [...statuses];
                next[i] = e.target.value as DayStatus;
                onStatuses(next);
                if (next[i] === "busy" || next[i] === "game") onLiftDays(liftDays.filter((d) => d !== i));
              }}
              aria-label={`${name} availability`}
              className={`${inputClass} px-1.5 py-1 text-xs`}
              style={inputStyle}
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-xs" style={{ color: canLift ? "var(--text-secondary)" : "var(--text-muted)" }}>
              <input
                type="checkbox"
                checked={lifting}
                disabled={!canLift}
                onChange={(e) => onLiftDays(e.target.checked ? [...liftDays, i].sort() : liftDays.filter((d) => d !== i))}
                aria-label={`Lift on ${name}`}
              />
              Lift
            </label>
          </div>
        );
      })}
    </div>
  );
}

export function Planner() {
  const [weekStart, setWeekStart] = useState(() => mondayOf(todayLocal()));
  const [week, setWeek] = useState<PlanWeek | null | undefined>(undefined);
  const [trainingDays, setTrainingDays] = useState<number[]>([0, 1, 3, 4]);
  const [statuses, setStatuses] = useState<DayStatus[]>(["open", "open", "open", "open", "open", "open", "open"]);
  const [saveUsual, setSaveUsual] = useState(true);
  const [showRebuild, setShowRebuild] = useState(false);
  const [building, setBuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .get<PlanWeek | null>(`/api/planner/week/${weekStart}`)
      .then((w) => {
        setWeek(w);
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, [weekStart]);

  useEffect(load, [load]);
  useEffect(() => {
    api
      .get<{ training_days: number[]; availability: DayStatus[] }>("/api/planner/defaults")
      .then((d) => {
        setTrainingDays(d.training_days);
        setStatuses(d.availability);
      })
      .catch(() => {});
  }, []);

  async function build() {
    if (!trainingDays.length) {
      setError("Pick at least one lifting day.");
      return;
    }
    setBuilding(true);
    setError(null);
    try {
      if (saveUsual) {
        await api.put("/api/planner/availability", statuses.map((status, weekday) => ({ weekday, status })));
      }
      setWeek(
        await api.post<PlanWeek>("/api/planner/generate", {
          week_start: weekStart,
          training_days: trainingDays,
          availability: statuses,
        }),
      );
      setShowRebuild(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't build the week.");
    } finally {
      setBuilding(false);
    }
  }

  const today = todayLocal();
  const isThisWeek = weekStart === mondayOf(today);
  const weekDates = Array.from({ length: 7 }, (_, i) => shiftDate(weekStart, i));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            Weekly Planner
          </h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Built from your own sessions, progression rules and running. Items tick off when you log them.
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => setWeekStart(shiftDate(weekStart, -7))} aria-label="Previous week" className="rounded-md p-1.5" style={secondaryButton}>
            <ChevronLeft size={16} />
          </button>
          <span className="w-40 text-center text-sm" style={{ color: "var(--text-primary)" }}>
            Week of {formatShortDate(weekStart).replace(/^\w+, /, "")}
          </span>
          <button onClick={() => setWeekStart(shiftDate(weekStart, 7))} aria-label="Next week" className="rounded-md p-1.5" style={secondaryButton}>
            <ChevronRight size={16} />
          </button>
          {!isThisWeek && (
            <button onClick={() => setWeekStart(mondayOf(today))} className="ml-1 rounded-md px-2.5 py-1.5 text-sm" style={secondaryButton}>
              This week
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="flex items-center gap-1.5 text-sm" style={{ color: "var(--status-critical)" }}>
          <AlertTriangle size={14} /> {error}
        </p>
      )}

      {week === undefined && !error && <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>}

      {(week === null || showRebuild) && (
        <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
          <div className="flex items-center gap-2">
            <CalendarRange size={18} style={{ color: "var(--text-muted)" }} />
            <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              {week ? "Rebuild this week" : "No plan for this week yet"}
            </h2>
          </div>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Mark each day as open, busy, or basketball, and tick the days you want to lift. Heavy leg work stays away from the
            day before a game, and basketball days replace runs.{week ? " Rebuilding replaces this week's plan, including any edits." : ""}
          </p>
          <WeekSetup statuses={statuses} liftDays={trainingDays} onStatuses={setStatuses} onLiftDays={setTrainingDays} />
          <label className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
            <input type="checkbox" checked={saveUsual} onChange={(e) => setSaveUsual(e.target.checked)} />
            Save this as my usual week (untick for a one-off schedule)
          </label>
          <div className="flex gap-2">
            <button onClick={build} disabled={building} className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50" style={primaryButton}>
              {building ? "Building…" : week ? "Rebuild week" : "Build my week"}
            </button>
            {week && (
              <button onClick={() => setShowRebuild(false)} className="rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
                Cancel
              </button>
            )}
          </div>
        </section>
      )}

      {week && (
        <>
          <section className="flex flex-col gap-2 rounded-lg border p-4" style={cardStyle}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm" style={{ color: "var(--text-primary)" }}>
                <strong>{week.done}</strong> of {week.total} done
              </p>
              <div className="flex gap-2">
                {!showRebuild && (
                  <button onClick={() => setShowRebuild(true)} className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
                    <RefreshCw size={14} /> Rebuild
                  </button>
                )}
                <a
                  href={`${API_BASE}/api/planner/week/${weekStart}/excel`}
                  className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm"
                  style={secondaryButton}
                >
                  <Download size={14} /> Excel
                </a>
              </div>
            </div>
            <div
              className="h-2 overflow-hidden rounded-full"
              style={{ background: "var(--surface-2)" }}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={week.total}
              aria-valuenow={week.done}
              aria-label="Week progress"
            >
              <div className="h-full rounded-full" style={{ width: `${week.total ? (week.done / week.total) * 100 : 0}%`, background: "var(--series-1)" }} />
            </div>
            {week.notes.map((n) => (
              <p key={n} className="text-xs" style={{ color: "var(--text-muted)" }}>
                {n}
              </p>
            ))}
          </section>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {week.days.map((d, i) => {
              const isToday = d.date === today;
              return (
                <section
                  key={d.date}
                  className="flex flex-col rounded-lg border p-4"
                  style={{ ...cardStyle, borderColor: isToday ? "var(--series-1)" : "var(--border-hairline)" }}
                >
                  <header className="mb-1 flex items-baseline justify-between gap-2">
                    <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                      {DAY_NAMES[i]} <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>{formatShortDate(d.date).replace(/^\w+, /, "")}</span>
                    </h3>
                    {isToday && (
                      <span className="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase" style={{ background: "var(--surface-2)", color: "var(--text-secondary)" }}>
                        Today
                      </span>
                    )}
                  </header>
                  <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    {d.focus}
                  </p>
                  {d.items.length > 0 ? (
                    <ul className="mt-1">
                      {d.items.map((it) => (
                        <PlanItemRow key={it.id} item={it} weekDates={weekDates} onChanged={load} />
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
                      Rest, walk, or light mobility.
                    </p>
                  )}
                </section>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
