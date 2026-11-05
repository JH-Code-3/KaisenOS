/** "8:30" from 8.5 minutes. */
export function formatPace(minutes: number | null): string {
  if (minutes == null) return "—";
  const total = Math.round(minutes * 60);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/** "1:05:30" / "27:45" from minutes. */
export function formatDuration(minutes: number | null): string {
  if (minutes == null) return "—";
  const total = Math.round(minutes * 60);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

/** "45", "27:30", "1:05:30" -> minutes. null if blank, NaN if unreadable. */
export function parseDuration(raw: string): number | null {
  const text = raw.trim();
  if (!text) return null;
  if (!/^\d+(:\d{1,2}){0,2}(\.\d+)?$/.test(text)) return NaN;
  const parts = text.split(":").map(Number);
  if (parts.slice(1).some((p) => p >= 60)) return NaN;
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return parts[0] + parts[1] / 60;
  return parts[0] * 60 + parts[1] + parts[2] / 60;
}

export const SESSION_LABELS: Record<string, string> = {
  running: "Run",
  sprint: "Sprints",
  plyometric: "Plyometrics",
  agility: "Agility",
  conditioning: "Conditioning",
  basketball: "Basketball",
};

export const BASKETBALL_LABELS: Record<string, string> = {
  practice: "Practice",
  game: "Game",
  skills: "Skills / shooting",
  pickup: "Pickup",
};

export const RUN_TYPE_LABELS: Record<string, string> = {
  easy: "Easy",
  recovery: "Recovery",
  long: "Long run",
  tempo: "Tempo",
  intervals: "Intervals",
  race: "Race / time trial",
};
