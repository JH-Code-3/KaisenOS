import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Apple,
  Dumbbell,
  Footprints,
  Moon,
  PersonStanding,
  Bot,
  CalendarRange,
  ClipboardPaste,
  Target,
  Settings as SettingsIcon,
  WifiOff,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/nutrition", label: "Nutrition", icon: Apple },
  { to: "/workouts", label: "Workouts", icon: Dumbbell },
  { to: "/running", label: "Sports & Running", icon: Footprints },
  { to: "/recovery", label: "Recovery", icon: Moon },
  { to: "/body", label: "Body Composition", icon: PersonStanding },
  { to: "/coach", label: "AI Coach", icon: Bot },
  { to: "/goals", label: "Goals & Phase", icon: Target },
  { to: "/import", label: "Import Notes", icon: ClipboardPaste },
  { to: "/planner", label: "Weekly Planner", icon: CalendarRange },
  { to: "/settings", label: "Settings / Privacy", icon: SettingsIcon },
];

export function Sidebar() {
  // "Basketball & Running" for basketball players, "Sports & Running" otherwise.
  const [runningLabel, setRunningLabel] = useState("Sports & Running");
  useEffect(() => {
    api
      .get<{ effective_sports: string[] }>("/api/coach/profile")
      .then((p) => setRunningLabel(p.effective_sports.includes("basketball") ? "Basketball & Running" : "Sports & Running"))
      .catch(() => {});
  }, []);

  return (
    <aside
      className="flex h-full w-60 flex-col border-r px-3 py-4"
      style={{ borderColor: "var(--border-hairline)", background: "var(--surface-1)" }}
    >
      <div className="mb-6 px-2">
        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          KaisenOS
        </p>
        <p className="mt-1 flex items-center gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
          <WifiOff size={12} /> Runs only on this computer
        </p>
      </div>

      <nav className="flex flex-1 flex-col gap-1">
        {NAV_ITEMS.map(({ to, label: baseLabel, icon: Icon }) => {
          const label = to === "/running" ? runningLabel : baseLabel;
          return (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors ${
                isActive ? "font-medium" : ""
              }`
            }
            style={({ isActive }) => ({
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              background: isActive ? "var(--surface-2)" : "transparent",
            })}
          >
            <Icon size={16} />
            {label}
          </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
