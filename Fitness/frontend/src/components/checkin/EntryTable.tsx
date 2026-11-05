import type { ReactNode } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { cardStyle } from "../../lib/ui";

export interface Column<T> {
  label: string;
  render: (row: T) => ReactNode;
  align?: "left" | "right";
}

interface Props<T extends { id: number }> {
  title: string;
  rows: T[];
  columns: Column<T>[];
  rowLabel: (row: T) => string;
  onEdit: (row: T) => void;
  onDelete: (row: T) => void;
  emptyText: string;
  /** Unique key per row (defaults to id). */
  rowKey?: (row: T) => string | number;
  /** Rows that can't be edited/deleted show this text instead of buttons. */
  readOnlyNote?: (row: T) => string | null;
}

/** History table; also the accessible table view for the charts above it. */
export function EntryTable<T extends { id: number }>({
  title,
  rows,
  columns,
  rowLabel,
  onEdit,
  onDelete,
  emptyText,
  rowKey = (row) => row.id,
  readOnlyNote = () => null,
}: Props<T>) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        {title}
      </h2>
      {rows.length === 0 ? (
        <div className="rounded-lg border p-6 text-sm" style={{ ...cardStyle, color: "var(--text-muted)" }}>
          {emptyText}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border" style={cardStyle}>
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="text-xs" style={{ color: "var(--text-muted)" }}>
                {columns.map((c) => (
                  <th key={c.label} className={`px-4 py-2 font-medium ${c.align === "right" ? "text-right" : "text-left"}`}>
                    {c.label}
                  </th>
                ))}
                <th className="w-16 px-4 py-2">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {rows.map((row) => (
                <tr key={rowKey(row)} className="border-t" style={{ borderColor: "var(--border-hairline)", color: "var(--text-secondary)" }}>
                  {columns.map((c) => (
                    <td key={c.label} className={`px-4 py-2 ${c.align === "right" ? "text-right" : ""}`}>
                      {c.render(row)}
                    </td>
                  ))}
                  <td className="px-4 py-2">
                    {readOnlyNote(row) ? (
                      <span className="block whitespace-nowrap text-right text-xs" style={{ color: "var(--text-muted)" }}>
                        {readOnlyNote(row)}
                      </span>
                    ) : (
                    <div className="flex justify-end gap-3" style={{ color: "var(--text-muted)" }}>
                      <button onClick={() => onEdit(row)} aria-label={`Edit ${rowLabel(row)}`} title="Edit">
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => {
                          if (window.confirm(`Delete ${rowLabel(row)}? This can't be undone.`)) onDelete(row);
                        }}
                        aria-label={`Delete ${rowLabel(row)}`}
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
