import { useState } from "react";
import { Plus, X } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { Food, Meal, MealIn, MealItemIn } from "../../lib/types";
import { formatShortDate } from "../../lib/dates";
import { EstimateTag } from "./EstimateTag";
import {
  cardStyle,
  inputClass,
  inputStyle,
  parseNumber,
  primaryButton,
  secondaryButton,
} from "../../lib/ui";

const MEAL_TYPES = ["Breakfast", "Lunch", "Dinner", "Snack", "Pre-workout", "Post-workout"];

const MACRO_FIELDS = [
  ["calories", "Cal"],
  ["protein_g", "Protein"],
  ["carbs_g", "Carbs"],
  ["fat_g", "Fat"],
] as const;
type MacroField = (typeof MACRO_FIELDS)[number][0];

// Macro values in the form are PER SERVING; they're multiplied by
// servings when building the payload (meal_items store eaten totals).
interface DraftItem {
  key: number;
  name: string;
  servings: string;
  unit: string;
  calories: string;
  protein_g: string;
  carbs_g: string;
  fat_g: string;
  isEstimate: boolean;
  foodId: number | null;
}

let nextKey = 1;
const newItem = (): DraftItem => ({
  key: nextKey++,
  name: "",
  servings: "1",
  unit: "",
  calories: "",
  protein_g: "",
  carbs_g: "",
  fat_g: "",
  isEstimate: false,
  foodId: null,
});

const ITEM_GRID = "grid grid-cols-[minmax(8rem,2fr)_4.5rem_5rem_repeat(4,minmax(3.5rem,1fr))_2.5rem_1.5rem] items-center gap-2";

const round1 = (n: number) => Math.round(n * 10) / 10;

function buildPayload(
  date: string,
  mealType: string,
  notes: string,
  items: DraftItem[],
  rememberFoods: boolean,
): { payload: MealIn; errors: string[] } {
  const errors: string[] = [];
  const out: MealItemIn[] = [];

  if (!date) errors.push("Pick a date.");

  items.forEach((item, index) => {
    const name = item.name.trim();
    const touched = name || item.calories || item.protein_g || item.carbs_g || item.fat_g;
    if (!touched) return;

    const label = name || `Food ${index + 1}`;
    if (!name) errors.push(`${label}: add a food name.`);

    const servings = parseNumber(item.servings);
    if (servings == null || Number.isNaN(servings) || servings <= 0) {
      errors.push(`${label}: servings must be more than 0.`);
      return;
    }

    const perServing = {} as Record<MacroField, number | null>;
    for (const [field, fieldLabel] of MACRO_FIELDS) {
      const value = parseNumber(item[field]);
      if (value != null && (Number.isNaN(value) || value < 0)) errors.push(`${label}: ${fieldLabel} can't be negative.`);
      perServing[field] = value;
    }
    if (perServing.calories == null) errors.push(`${label}: calories are required.`);

    const total = (v: number | null) => (v == null ? null : round1(v * servings));

    out.push({
      food_name: name,
      quantity: servings,
      serving_unit: item.unit.trim() || null,
      calories: total(perServing.calories),
      protein_g: total(perServing.protein_g),
      carbs_g: total(perServing.carbs_g),
      fat_g: total(perServing.fat_g),
      food_id: item.foodId,
      is_estimate: item.isEstimate,
      save_as_food: rememberFoods && item.foodId == null,
    });
  });

  if (errors.length === 0 && out.length === 0) errors.push("Add at least one food.");

  return {
    payload: { meal_date: date, meal_type: mealType || null, notes: notes.trim() || null, items: out },
    errors,
  };
}

interface Props {
  date: string;
  foods: Food[];
  onSaved: (meal: Meal) => void;
  onCancel: () => void;
}

export function LogMealForm({ date: initialDate, foods, onSaved, onCancel }: Props) {
  const [date, setDate] = useState(initialDate);
  const [mealType, setMealType] = useState(() => guessMealType());
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<DraftItem[]>([newItem()]);
  const [rememberFoods, setRememberFoods] = useState(true);
  const [errors, setErrors] = useState<string[]>([]);
  const [review, setReview] = useState<MealIn | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const foodsByName = new Map(foods.map((f) => [f.name.toLowerCase(), f]));

  function updateItem(key: number, patch: Partial<DraftItem>) {
    setItems((list) => list.map((i) => (i.key === key ? { ...i, ...patch } : i)));
  }

  function changeName(item: DraftItem, name: string) {
    const saved = foodsByName.get(name.trim().toLowerCase());
    if (saved) {
      // Picked a saved food: fill in its per-serving values.
      updateItem(item.key, {
        name: saved.name,
        unit: saved.serving_unit ?? "",
        calories: saved.calories?.toString() ?? "",
        protein_g: saved.protein_g?.toString() ?? "",
        carbs_g: saved.carbs_g?.toString() ?? "",
        fat_g: saved.fat_g?.toString() ?? "",
        isEstimate: Boolean(saved.is_estimate),
        foodId: saved.id,
      });
    } else {
      updateItem(item.key, { name, foodId: null });
    }
  }

  function goToReview() {
    const result = buildPayload(date, mealType, notes, items, rememberFoods);
    setErrors(result.errors);
    if (result.errors.length === 0) {
      setSaveError(null);
      setReview(result.payload);
    }
  }

  async function save() {
    if (!review) return;
    setSaving(true);
    setSaveError(null);
    try {
      onSaved(await api.post<Meal>("/api/nutrition/meals", review));
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  // ---------- Review step: nothing is written until "Save" ----------
  if (review) {
    const sum = (field: MacroField) => round1(review.items.reduce((s, i) => s + (i[field] ?? 0), 0));
    const newFoods = review.items.filter((i) => i.save_as_food).map((i) => i.food_name);

    return (
      <section className="flex flex-col gap-4 rounded-lg border p-4" style={cardStyle}>
        <div>
          <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Review before saving
          </h2>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {review.meal_type ?? "Meal"} · {formatShortDate(review.meal_date)}
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[32rem] text-sm" style={{ color: "var(--text-secondary)" }}>
            <thead>
              <tr className="text-left text-xs" style={{ color: "var(--text-muted)" }}>
                <th className="py-1 font-medium">Food</th>
                <th className="py-1 font-medium">Amount</th>
                <th className="py-1 text-right font-medium">Cal</th>
                <th className="py-1 text-right font-medium">P</th>
                <th className="py-1 text-right font-medium">C</th>
                <th className="py-1 text-right font-medium">F</th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {review.items.map((i, idx) => (
                <tr key={idx} className="border-t" style={{ borderColor: "var(--border-hairline)" }}>
                  <td className="py-1">
                    {i.food_name}
                    {i.is_estimate && <EstimateTag />}
                  </td>
                  <td className="py-1">
                    {i.quantity} {i.serving_unit ?? (i.quantity === 1 ? "serving" : "servings")}
                  </td>
                  <td className="py-1 text-right">{i.calories ?? "—"}</td>
                  <td className="py-1 text-right">{i.protein_g ?? "—"}</td>
                  <td className="py-1 text-right">{i.carbs_g ?? "—"}</td>
                  <td className="py-1 text-right">{i.fat_g ?? "—"}</td>
                </tr>
              ))}
              <tr className="border-t font-medium" style={{ borderColor: "var(--baseline)", color: "var(--text-primary)" }}>
                <td className="py-1">Total</td>
                <td />
                <td className="py-1 text-right">{sum("calories")}</td>
                <td className="py-1 text-right">{sum("protein_g")}</td>
                <td className="py-1 text-right">{sum("carbs_g")}</td>
                <td className="py-1 text-right">{sum("fat_g")}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {newFoods.length > 0 && (
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            Will be added to My foods: {newFoods.join(", ")}
          </p>
        )}
        {review.notes && (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Notes: {review.notes}
          </p>
        )}
        {saveError && (
          <p className="text-sm" style={{ color: "var(--status-critical)" }}>
            Couldn&rsquo;t save: {saveError}
          </p>
        )}

        <div className="flex gap-2">
          <button
            onClick={save}
            disabled={saving}
            className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-50"
            style={primaryButton}
          >
            {saving ? "Saving…" : "Save meal"}
          </button>
          <button onClick={() => setReview(null)} disabled={saving} className="rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
            Back to edit
          </button>
        </div>
      </section>
    );
  }

  // ---------- Entry step ----------
  return (
    <section className="flex flex-col gap-4 rounded-lg border p-4" style={cardStyle}>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Log a meal
        </h2>
        <button onClick={onCancel} aria-label="Close" style={{ color: "var(--text-muted)" }}>
          <X size={16} />
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[10rem_12rem]">
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} style={inputStyle} />
        </label>
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
          Meal
          <select
            value={mealType}
            onChange={(e) => setMealType(e.target.value)}
            aria-label="Meal type"
            className={inputClass}
            style={inputStyle}
          >
            {MEAL_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      </div>

      <datalist id="saved-foods">
        {foods.map((f) => (
          <option key={f.id} value={f.name} />
        ))}
      </datalist>

      <div className="overflow-x-auto">
        <div className="flex min-w-[44rem] flex-col gap-2">
          <div className={`${ITEM_GRID} text-xs`} style={{ color: "var(--text-muted)" }}>
            <span>Food</span>
            <span>Servings</span>
            <span>Unit</span>
            <span>Cal / serving</span>
            <span>Protein g</span>
            <span>Carbs g</span>
            <span>Fat g</span>
            <span title="Mark values you guessed">Est.</span>
            <span />
          </div>

          {items.map((item, index) => {
            const servings = parseNumber(item.servings) ?? 0;
            const perCal = parseNumber(item.calories);
            const showTotal = perCal != null && !Number.isNaN(perCal) && servings > 0 && servings !== 1;

            return (
              <div key={item.key} className="flex flex-col gap-0.5">
                <div className={ITEM_GRID}>
                  <input
                    list="saved-foods"
                    value={item.name}
                    onChange={(e) => changeName(item, e.target.value)}
                    placeholder={foods.length ? "Type or pick a saved food" : "e.g. Greek yogurt"}
                    aria-label={`Food ${index + 1} name`}
                    className={`${inputClass} min-w-0`}
                    style={inputStyle}
                  />
                  <input
                    type="number"
                    min={0}
                    step="0.25"
                    inputMode="decimal"
                    value={item.servings}
                    onChange={(e) => updateItem(item.key, { servings: e.target.value })}
                    aria-label={`Food ${index + 1} servings`}
                    className={`${inputClass} min-w-0`}
                    style={inputStyle}
                  />
                  <input
                    value={item.unit}
                    onChange={(e) => updateItem(item.key, { unit: e.target.value })}
                    placeholder="serving"
                    aria-label={`Food ${index + 1} unit`}
                    className={`${inputClass} min-w-0`}
                    style={inputStyle}
                  />
                  {MACRO_FIELDS.map(([field, label]) => (
                    <input
                      key={field}
                      type="number"
                      min={0}
                      inputMode="decimal"
                      value={item[field]}
                      onChange={(e) => updateItem(item.key, { [field]: e.target.value })}
                      aria-label={`Food ${index + 1} ${label} per serving`}
                      className={`${inputClass} min-w-0`}
                      style={inputStyle}
                    />
                  ))}
                  <input
                    type="checkbox"
                    checked={item.isEstimate}
                    onChange={(e) => updateItem(item.key, { isEstimate: e.target.checked })}
                    aria-label={`Food ${index + 1} values are an estimate`}
                    className="h-4 w-4 justify-self-center"
                  />
                  {items.length > 1 ? (
                    <button
                      onClick={() => setItems((list) => list.filter((i) => i.key !== item.key))}
                      aria-label={`Remove food ${index + 1}`}
                      style={{ color: "var(--text-muted)" }}
                    >
                      <X size={14} />
                    </button>
                  ) : (
                    <span />
                  )}
                </div>
                {(item.foodId != null || showTotal) && (
                  <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {item.foodId != null ? "From My foods" : ""}
                    {item.foodId != null && showTotal ? " · " : ""}
                    {showTotal ? `${round1(perCal! * servings)} kcal total` : ""}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <button
          onClick={() => setItems((list) => [...list, newItem()])}
          className="flex items-center gap-1 rounded-md px-3 py-1.5 text-sm"
          style={secondaryButton}
        >
          <Plus size={14} /> Add food
        </button>
        <label className="flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
          <input type="checkbox" checked={rememberFoods} onChange={(e) => setRememberFoods(e.target.checked)} />
          Remember new foods in My foods
        </label>
      </div>

      <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
        Notes (optional)
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className={inputClass}
          style={inputStyle}
        />
      </label>

      {errors.length > 0 && (
        <ul className="list-disc pl-5 text-sm" style={{ color: "var(--status-critical)" }}>
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}

      <div className="flex gap-2">
        <button onClick={goToReview} className="rounded-md px-3 py-1.5 text-sm font-medium" style={primaryButton}>
          Review
        </button>
        <button onClick={onCancel} className="rounded-md px-3 py-1.5 text-sm" style={secondaryButton}>
          Cancel
        </button>
      </div>
    </section>
  );
}

/** Default the meal type from the time of day. */
function guessMealType(): string {
  const hour = new Date().getHours();
  if (hour < 11) return "Breakfast";
  if (hour < 15) return "Lunch";
  if (hour < 20) return "Dinner";
  return "Snack";
}
