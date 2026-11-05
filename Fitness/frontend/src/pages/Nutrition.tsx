import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { Food, Meal, NutritionDay, WeeklyNutrition } from "../lib/types";
import { formatShortDate, shiftDate, todayLocal } from "../lib/dates";
import { cardStyle, inputClass, inputStyle, primaryButton, secondaryButton } from "../lib/ui";
import { StatCard } from "../components/StatCard";
import { WeeklyCaloriesChart } from "../components/WeeklyCaloriesChart";
import { MacroProgress } from "../components/nutrition/MacroProgress";
import { TargetsForm } from "../components/nutrition/TargetsForm";
import { LogMealForm } from "../components/nutrition/LogMealForm";
import { MealCard } from "../components/nutrition/MealCard";

export function Nutrition() {
  const [date, setDate] = useState(todayLocal());
  const [day, setDay] = useState<NutritionDay | null>(null);
  const [week, setWeek] = useState<WeeklyNutrition | null>(null);
  const [foods, setFoods] = useState<Food[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<"none" | "meal" | "targets">("none");
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([
      api.get<NutritionDay>(`/api/nutrition/day/${date}`),
      api.get<WeeklyNutrition>(`/api/nutrition/weekly-average?end_date=${date}`),
      api.get<Food[]>("/api/nutrition/foods"),
    ])
      .then(([dayData, weekData, foodList]) => {
        setDay(dayData);
        setWeek(weekData);
        setFoods(foodList);
        setError(null);
      })
      .catch((err: ApiError) => setError(err.message));
  }, [date]);

  useEffect(refresh, [refresh]);

  function changeDate(next: string) {
    if (!next) return;
    setDate(next);
    setNotice(null);
  }

  async function deleteMeal(meal: Meal) {
    try {
      await api.delete(`/api/nutrition/meals/${meal.id}`);
      setNotice("Meal deleted.");
      refresh();
    } catch (err) {
      setNotice(err instanceof ApiError ? `Couldn't delete: ${err.message}` : "Couldn't delete.");
    }
  }

  if (error) {
    return (
      <div
        className="flex items-start gap-2 rounded-lg border p-4 text-sm"
        style={{ borderColor: "var(--status-critical)", color: "var(--text-primary)", background: "var(--surface-1)" }}
      >
        <AlertTriangle size={16} style={{ color: "var(--status-critical)" }} />
        <div>
          <p className="font-medium">Can&rsquo;t reach the backend</p>
          <p style={{ color: "var(--text-secondary)" }}>{error}</p>
        </div>
      </div>
    );
  }

  if (!day || !week) {
    return <p style={{ color: "var(--text-muted)" }}>Loading&hellip;</p>;
  }

  const isToday = date === todayLocal();
  const isEmpty = day.meals.length === 0 && day.legacy_entries.length === 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            Nutrition
          </h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            {isToday ? "Today" : formatShortDate(date)}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1">
            <button
              onClick={() => changeDate(shiftDate(date, -1))}
              aria-label="Previous day"
              className="rounded-md p-1.5"
              style={secondaryButton}
            >
              <ChevronLeft size={16} />
            </button>
            <input
              type="date"
              value={date}
              onChange={(e) => changeDate(e.target.value)}
              aria-label="Date"
              className={inputClass}
              style={inputStyle}
            />
            <button
              onClick={() => changeDate(shiftDate(date, 1))}
              aria-label="Next day"
              className="rounded-md p-1.5"
              style={secondaryButton}
            >
              <ChevronRight size={16} />
            </button>
            {!isToday && (
              <button onClick={() => changeDate(todayLocal())} className="rounded-md px-2.5 py-1.5 text-sm" style={secondaryButton}>
                Today
              </button>
            )}
          </div>
          {panel !== "meal" && (
            <button
              onClick={() => {
                setPanel("meal");
                setNotice(null);
              }}
              className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium"
              style={primaryButton}
            >
              <Plus size={15} /> Log meal
            </button>
          )}
        </div>
      </div>

      {notice && (
        <p className="flex items-center gap-1.5 text-sm" style={{ color: "var(--text-secondary)" }}>
          <CheckCircle2 size={15} style={{ color: "var(--status-good)" }} /> {notice}
        </p>
      )}

      {panel === "targets" ? (
        <TargetsForm
          effectiveDate={date}
          current={day.target}
          onCancel={() => setPanel("none")}
          onSaved={() => {
            setPanel("none");
            setNotice("Targets saved.");
            refresh();
          }}
        />
      ) : (
        <MacroProgress totals={day.totals} target={day.target} onEditTargets={() => setPanel("targets")} />
      )}

      {panel === "meal" && (
        <LogMealForm
          key={date}
          date={date}
          foods={foods}
          onCancel={() => setPanel("none")}
          onSaved={(meal) => {
            setPanel("none");
            setNotice(`Saved ${meal.meal_type ?? "meal"} — ${meal.items.length} food${meal.items.length === 1 ? "" : "s"}.`);
            if (meal.meal_date !== date) setDate(meal.meal_date);
            else refresh();
          }}
        />
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Meals
        </h2>

        {isEmpty && (
          <div className="rounded-lg border p-6 text-sm" style={{ ...cardStyle, color: "var(--text-muted)" }}>
            Nothing logged for {isToday ? "today" : formatShortDate(date)}. Use <strong>Log meal</strong> to add one.
          </div>
        )}

        {day.meals.map((meal) => (
          <MealCard key={meal.id} meal={meal} onDelete={deleteMeal} />
        ))}

        {day.legacy_entries.map((entry) => (
          <article key={`legacy-${entry.id}`} className="flex flex-col gap-1 rounded-lg border p-4" style={cardStyle}>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Daily total from CLI coach
            </h3>
            <p className="text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
              {entry.calories ?? "—"} kcal · P {entry.protein_g ?? "—"}g · C {entry.carbs_g ?? "—"}g · F {entry.fat_g ?? "—"}g
            </p>
            {entry.notes && (
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                {entry.notes}
              </p>
            )}
          </article>
        ))}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          7 days ending {isToday ? "today" : formatShortDate(date)}
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Avg calories"
            value={Math.round(week.avg_calories).toLocaleString()}
            unit="kcal"
            sublabel={`over ${week.days_logged} logged day${week.days_logged === 1 ? "" : "s"}`}
            isEmpty={week.days_logged === 0}
            emptyText="No days logged"
          />
          <StatCard
            label="Avg protein"
            value={Math.round(week.avg_protein_g)}
            unit="g"
            sublabel={day.target?.protein_g ? `target ${Math.round(day.target.protein_g)} g` : undefined}
            isEmpty={week.days_logged === 0}
            emptyText="No days logged"
          />
          <StatCard
            label="Days logged"
            value={`${week.days_logged} / 7`}
            isEmpty={false}
          />
        </div>
        <WeeklyCaloriesChart days={week.days} />
      </section>
    </div>
  );
}
