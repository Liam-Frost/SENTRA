import { useMemo } from "react";

import type { ThemeMode } from "./ThemeToggle";
import type { RouteKey } from "./DockNav";

type TopBarProps = {
  route: RouteKey;
  connectionLabel: string;
  hasError: boolean;
  tick: number;
  incidentCount: number;
  autonomyEnabled: boolean;
  lastUpdated: Date | null;
  themeMode: ThemeMode;
};

const routeLabels: Record<RouteKey, string> = {
  dashboard: "Dashboard",
  fleet: "Fleet",
  incidents: "Incidents",
  policies: "Policies",
  operations: "Operations",
  actions: "Actions",
  nodes: "Node"
};

export default function TopBar({
  route,
  connectionLabel,
  hasError,
  tick,
  incidentCount,
  autonomyEnabled,
  lastUpdated
}: TopBarProps) {
  const pageLabel = useMemo(() => routeLabels[route] ?? "Dashboard", [route]);
  const lastUpdatedLabel = lastUpdated ? lastUpdated.toLocaleTimeString() : "-";

  return (
    <header className="topbar" aria-label="Top bar">
      <div className="topbar-left">
        <div className="topbar-brand">
          <div className="topbar-logo">SENTRA</div>
          <div className="topbar-sep" role="presentation" />
          <div className="topbar-page">{pageLabel}</div>
        </div>

        <div className="topbar-chips" aria-label="Status summary">
          <div className="status-chip">Tick {tick}</div>
          <div className="status-chip">Incidents {incidentCount}</div>
          <div className="status-chip">
            Autonomy {autonomyEnabled ? "Enabled" : "Standby"}
          </div>
        </div>
      </div>

      <div className="topbar-right">
        <div className="status-pill">
          <span className={`dot ${hasError ? "dot-warn" : "dot-ok"}`} />
          <span>{connectionLabel}</span>
        </div>
        <div className="topbar-meta">
          <span className="topbar-meta-item">Updated {lastUpdatedLabel}</span>
        </div>
      </div>
    </header>
  );
}
