// Shared styling for form controls and cards.

export const inputStyle = {
  background: "var(--surface-2)",
  borderColor: "var(--border-hairline)",
  color: "var(--text-primary)",
};

export const inputClass = "rounded-md border px-2 py-1.5 text-sm outline-none focus:border-[var(--series-1)]";

export const cardStyle = { borderColor: "var(--border-hairline)", background: "var(--surface-1)" };

export const primaryButton = { background: "var(--series-1)", color: "#fff" };
export const secondaryButton = { background: "var(--surface-2)", color: "var(--text-primary)" };

/** "" -> null, otherwise Number (may be NaN; callers validate). */
export function parseNumber(raw: string): number | null {
  return raw.trim() === "" ? null : Number(raw);
}

/** Scroll the main content pane (not the window — <main> is the scroller). */
export function scrollToTop() {
  document.querySelector("main")?.scrollTo({ top: 0, behavior: "smooth" });
}
