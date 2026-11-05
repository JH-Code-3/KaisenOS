import { AlertTriangle } from "lucide-react";
import type { CoachStatus } from "../../lib/types";
import { cardStyle } from "../../lib/ui";

const STALE_HOURS = 48;

/** Problem with the Garmin sync, or null if it's fine / not set up. */
function garminSyncProblem(status: CoachStatus): string | null {
  const g = status.garmin;
  if (!g) return null;
  if (g.status === "failed") return g.error ?? "The last Garmin sync failed.";
  const finished = g.finished_at ?? g.started_at;
  const hours = (Date.now() - new Date(finished.endsWith("Z") || finished.includes("+") ? finished : `${finished}Z`).getTime()) / 3_600_000;
  if (hours > STALE_HOURS) {
    const days = Math.floor(hours / 24);
    return status.garmin_schedule_on
      ? `Garmin hasn't synced in ${days} days. Your Mac may have been off or asleep at 8:00 am. Open the Garmin Connect app on your phone, then run the sync by hand or wait for tomorrow's.`
      : `Garmin hasn't synced in ${days} days, so readiness is using older data.`;
  }
  return null;
}

export function GarminSyncWarning({ status }: { status: CoachStatus }) {
  const problem = garminSyncProblem(status);
  if (!problem) return null;
  return (
    <div className="flex items-start gap-2 rounded-lg border p-3 text-sm" style={{ ...cardStyle, borderColor: "var(--status-warning)" }}>
      <AlertTriangle size={15} style={{ color: "var(--status-warning)", flexShrink: 0, marginTop: 2 }} />
      <div style={{ color: "var(--text-secondary)" }}>
        <p className="font-medium" style={{ color: "var(--text-primary)" }}>
          Garmin sync needs attention
        </p>
        <p>{problem}</p>
      </div>
    </div>
  );
}
