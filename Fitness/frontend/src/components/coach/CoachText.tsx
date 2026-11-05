/** Inline **bold** / *italic* as React nodes (never as HTML). */
function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : part.length > 2 && part.startsWith("*") && part.endsWith("*") ? (
      <em key={i}>{part.slice(1, -1)}</em>
    ) : (
      part
    ),
  );
}

/** Minimal, safe rendering of the model's light markdown: paragraphs, bullets, headings, bold. */
export function CoachText({ text }: { text: string }) {
  const blocks: { type: "p" | "ul"; lines: string[] }[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
      blocks.push({ type: "p", lines: [] }); // "---" divider -> paragraph break
      continue;
    }
    const bullet = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (!line.trim()) {
      blocks.push({ type: "p", lines: [] });
    } else if (bullet) {
      const last = blocks[blocks.length - 1];
      if (last?.type === "ul") last.lines.push(bullet[1]);
      else blocks.push({ type: "ul", lines: [bullet[1]] });
    } else {
      const last = blocks[blocks.length - 1];
      const clean = line.replace(/^#{1,6}\s+/, "");
      if (last?.type === "p" && last.lines.length) last.lines.push(clean);
      else blocks.push({ type: "p", lines: [clean] });
    }
  }

  return (
    <div className="flex flex-col gap-2 text-sm leading-relaxed" style={{ color: "var(--text-primary)" }}>
      {blocks
        .filter((b) => b.lines.length)
        .map((b, i) =>
          b.type === "ul" ? (
            <ul key={i} className="list-disc pl-5">
              {b.lines.map((l, j) => (
                <li key={j}>{inline(l)}</li>
              ))}
            </ul>
          ) : (
            <p key={i}>
              {b.lines.map((l, j) => (
                <span key={j}>
                  {j > 0 && <br />}
                  {inline(l)}
                </span>
              ))}
            </p>
          ),
        )}
    </div>
  );
}
