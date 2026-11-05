import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { api, ApiError } from "../../lib/api";
import type { ChatMessage } from "../../lib/types";
import { cardStyle, inputClass, inputStyle, primaryButton } from "../../lib/ui";
import { CoachText } from "./CoachText";

interface Props {
  enabled: boolean;
  title?: string;
  placeholderExamples: string;
  /** Optional opening messages (initial only; remount with a new `key` to reset). */
  seed?: ChatMessage[];
}

/** Chat with the local coach. History stays in this page only. */
export function CoachChat({ enabled, title = "Ask the coach", placeholderExamples, seed }: Props) {
  const [chat, setChat] = useState<ChatMessage[]>(() => seed ?? []);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  // Keep the newest message in view, but don't scroll the page on first load.
  useEffect(() => {
    if (chat.length > (seed?.length ?? 0) || busy) end.current?.scrollIntoView({ block: "nearest" });
  }, [chat, busy, seed]);

  async function send() {
    const question = draft.trim();
    if (!question || busy) return;
    const history = chat;
    setChat([...history, { role: "user", content: question }]);
    setDraft("");
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ text: string }>("/api/coach/ask", { task: "chat", question, history });
      setChat((c) => [...c, { role: "assistant", content: res.text }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The coach didn't respond.");
      setChat(history);
      setDraft(question);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4" style={cardStyle}>
      <h2 className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        {title}
      </h2>
      {chat.length === 0 && (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          e.g. {placeholderExamples} General training guidance only — for pain or injuries, see a doctor or physical
          therapist.
        </p>
      )}
      <div className="flex flex-col gap-3" aria-live="polite">
        {chat.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-lg px-3 py-2 ${m.role === "user" ? "self-end" : "self-start"}`}
            style={{
              background: m.role === "user" ? "var(--surface-2)" : "transparent",
              border: m.role === "assistant" ? "1px solid var(--border-hairline)" : undefined,
            }}
          >
            {m.role === "assistant" ? (
              <CoachText text={m.content} />
            ) : (
              <p className="whitespace-pre-wrap text-sm" style={{ color: "var(--text-primary)" }}>
                {m.content}
              </p>
            )}
          </div>
        ))}
        {busy && (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Thinking&hellip; (local models can take a minute)
          </p>
        )}
        <div ref={end} />
      </div>
      {error && (
        <p className="text-sm" style={{ color: "var(--status-critical)" }}>
          {error}
        </p>
      )}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={enabled ? "Ask about your training…" : "Local model not available"}
          disabled={!enabled}
          aria-label="Message the coach"
          className={`${inputClass} flex-1`}
          style={inputStyle}
        />
        <button
          type="submit"
          disabled={!enabled || busy || !draft.trim()}
          aria-label="Send"
          className="rounded-md px-3 py-1.5 disabled:opacity-50"
          style={primaryButton}
        >
          <Send size={15} />
        </button>
      </form>
    </section>
  );
}
