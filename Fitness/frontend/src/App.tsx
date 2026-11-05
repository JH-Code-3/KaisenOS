import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Sidebar } from "./components/Sidebar";
import { Overview } from "./pages/Overview";
import { Settings } from "./pages/Settings";
import { Workouts } from "./pages/Workouts";
import { Nutrition } from "./pages/Nutrition";
import { Running } from "./pages/Running";
import { Recovery } from "./pages/Recovery";
import { Body } from "./pages/Body";
import { Coach } from "./pages/Coach";
import { Goals } from "./pages/Goals";
import { Import } from "./pages/Import";
import { Planner } from "./pages/Planner";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen" style={{ background: "var(--surface-0)" }}>
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/nutrition" element={<Nutrition />} />
            <Route path="/workouts" element={<Workouts />} />
            <Route path="/running" element={<Running />} />
            <Route path="/recovery" element={<Recovery />} />
            <Route path="/body" element={<Body />} />
            <Route path="/coach" element={<Coach />} />
            <Route path="/goals" element={<Goals />} />
            <Route path="/import" element={<Import />} />
            <Route path="/planner" element={<Planner />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
