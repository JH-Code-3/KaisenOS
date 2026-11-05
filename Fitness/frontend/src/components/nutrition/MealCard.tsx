import { useState } from "react";
import { Trash2 } from "lucide-react";
import type { Meal } from "../../lib/types";
import { cardStyle } from "../../lib/ui";
import { EstimateTag } from "./EstimateTag";

const fmt = (n: number | null) => (n == null ? "—" : Math.round(n).toLocaleString());

interface Props {
  meal: Meal;
  onDelete: (meal: Meal) => Promise<void>;
}

export function MealCard({ meal, onDelete }: Props) {
  const [deleting, setDeleting] = useState(false);
  const sum = (field: "calories" | "protein_g" | "carbs_g" | "fat_g") =>
    meal.items.reduce((s, i) => s + (i[field] ?? 0), 0);

  async function handleDelete() {
    const label = meal.meal_type ?? "this meal";
    if (!window.confirm(`Delete ${label} (${meal.items.length} food${meal.items.length === 1 ? "" : "s"})? This can't be undone.`)) return;
    setDeleting(true);
    try {
      await onDelete(meal);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <article className="flex flex-col gap-2 rounded-lg border p-4" style={{ ...cardStyle, opacity: deleting ? 0.5 : 1 }}>
      <header className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            {meal.meal_type ?? "Meal"}
          </h3>
          <p className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>
            {fmt(sum("calories"))} kcal · P {fmt(sum("protein_g"))}g · C {fmt(sum("carbs_g"))}g · F {fmt(sum("fat_g"))}g
          </p>
        </div>
        <button onClick={handleDelete} disabled={deleting} aria-label="Delete meal" title="Delete meal" style={{ color: "var(--text-muted)" }}>
          <Trash2 size={15} />
        </button>
      </header>

      <ul className="flex flex-col">
        {meal.items.map((item) => (
          <li
            key={item.id}
            className="flex flex-wrap items-baseline justify-between gap-x-4 border-t py-1.5 text-sm"
            style={{ borderColor: "var(--border-hairline)" }}
          >
            <span style={{ color: "var(--text-primary)" }}>
              {item.food_name}
              <span style={{ color: "var(--text-muted)" }}>
                {" "}
                · {item.quantity} {item.serving_unit ?? (item.quantity === 1 ? "serving" : "servings")}
              </span>
              {item.is_estimate ? <EstimateTag /> : null}
            </span>
            <span className="text-xs tabular-nums" style={{ color: "var(--text-secondary)" }}>
              {fmt(item.calories)} kcal · P {fmt(item.protein_g)} · C {fmt(item.carbs_g)} · F {fmt(item.fat_g)}
            </span>
          </li>
        ))}
      </ul>

      {meal.notes && (
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          {meal.notes}
        </p>
      )}
    </article>
  );
}
