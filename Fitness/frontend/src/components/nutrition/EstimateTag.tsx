export function EstimateTag() {
  return (
    <span
      className="ml-1.5 rounded px-1 py-0.5 text-[10px] font-medium uppercase"
      style={{ color: "var(--text-muted)", background: "var(--surface-2)" }}
      title="Values are an estimate"
    >
      est.
    </span>
  );
}
