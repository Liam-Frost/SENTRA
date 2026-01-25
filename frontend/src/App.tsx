import { useEffect, useMemo, useRef, useState } from "react";
import DockNav, { type RouteKey } from "./components/DockNav";
import ControlDrawer from "./components/ControlDrawer";
import NotificationTray, { type NotificationItem } from "./components/NotificationTray";
import type { ServerState, WorldState } from "./types";
import { useSentra } from "./state/useSentra";
import Dashboard from "./pages/Dashboard";
import ServerFleet from "./pages/ServerFleet";
import EventTimeline from "./pages/EventTimeline";
import { isIncident } from "./utils/metrics";
import type { ThemeMode } from "./components/ThemeToggle";

const THEME_STORAGE_KEY = "sentra-theme-mode";
const NOTIFICATION_TTL = 8000;

const defaultServer: ServerState = {
  load: 0,
  temp: 0,
  error_rate: 0,
  power: 0,
  health: 100,
  cooling: false,
  cooling_level: 0,
  status: "booting"
};

const fallbackState: WorldState = {
  tick: 0,
  incoming_traffic: 0,
  autonomy_enabled: false,
  servers: {
    S1: { ...defaultServer },
    S2: { ...defaultServer },
    S3: { ...defaultServer }
  }
};

const routes: RouteKey[] = ["dashboard", "fleet", "events"];

function parseRoute(): RouteKey {
  const raw = window.location.hash.replace("#/", "").replace("#", "");
  const routeKey = raw.split("?")[0];
  if (routes.includes(routeKey as RouteKey)) return routeKey as RouteKey;
  return "dashboard";
}

function useHashRoute() {
  const [route, setRoute] = useState<RouteKey>(() => parseRoute());

  useEffect(() => {
    const handler = () => setRoute(parseRoute());
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  const navigate = (next: RouteKey) => {
    window.location.hash = `/${next}`;
  };

  return { route, navigate };
}

function getSystemTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(mode: ThemeMode) {
  const theme = mode === "system" ? getSystemTheme() : mode;
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.themeMode = mode;
}

export default function App() {
  const {
    state,
    events,
    loading,
    error,
    busy,
    lastUpdated,
    realtime,
    advanceTick,
    toggleAutonomy,
    injectFault,
    reset,
    setRealtime
  } = useSentra();

  const displayState = state ?? fallbackState;
  const incidentCount = useMemo(() => {
    return Object.values(displayState.servers).filter(isIncident).length;
  }, [displayState.servers]);

  const { route, navigate } = useHashRoute();
  const [toolsOpen, setToolsOpen] = useState(false);
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null;
    return stored ?? "system";
  });

  const [notifications, setNotifications] = useState<
    (NotificationItem & { expiresAt: number })[]
  >([]);
  const lastIncidentIdRef = useRef(0);

  useEffect(() => {
    if (!window.location.hash) {
      window.location.hash = "/dashboard";
    }
  }, []);

  useEffect(() => {
    const handleControlRoute = () => {
      const raw = window.location.hash.replace("#/", "").replace("#", "");
      const base = raw.split("?")[0];
      if (base !== "control") return;
      setToolsOpen(true);
      window.location.hash = "/dashboard";
    };

    handleControlRoute();
    window.addEventListener("hashchange", handleControlRoute);
    return () => window.removeEventListener("hashchange", handleControlRoute);
  }, []);

  useEffect(() => {
    applyTheme(themeMode);
    window.localStorage.setItem(THEME_STORAGE_KEY, themeMode);
  }, [themeMode]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (themeMode === "system") {
        applyTheme("system");
      }
    };

    if (media.addEventListener) {
      media.addEventListener("change", handler);
    } else {
      media.addListener(handler);
    }

    return () => {
      if (media.removeEventListener) {
        media.removeEventListener("change", handler);
      } else {
        media.removeListener(handler);
      }
    };
  }, [themeMode]);

  useEffect(() => {
    if (events.length === 0) {
      lastIncidentIdRef.current = 0;
      return;
    }

    const newIncidents = events.filter(
      (event) => event.type === "incident" && event.id > lastIncidentIdRef.current
    );

    if (newIncidents.length === 0) return;

    const maxId = Math.max(...newIncidents.map((event) => event.id));
    lastIncidentIdRef.current = Math.max(lastIncidentIdRef.current, maxId);

    const now = Date.now();
    const nextNotifications = newIncidents
      .sort((a, b) => b.id - a.id)
      .map((event) => ({
        id: event.id,
        message: event.message,
        tick: event.tick,
        ts: event.ts,
        expiresAt: now + NOTIFICATION_TTL
      }));

    setNotifications((current) => [...nextNotifications, ...current].slice(0, 4));
  }, [events]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      const now = Date.now();
      setNotifications((current) =>
        current.filter((item) => item.expiresAt > now)
      );
    }, 1000);

    return () => window.clearInterval(interval);
  }, []);

  const connectionLabel = loading ? "Connecting" : error ? "Degraded" : "Live";
  const handleReset = async (resetEvents: boolean) => {
    await reset(resetEvents);
    setNotifications([]);
    if (resetEvents) {
      lastIncidentIdRef.current = 0;
      return;
    }
    const maxId = events.length > 0 ? Math.max(...events.map((event) => event.id)) : 0;
    lastIncidentIdRef.current = maxId;
  };

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="title-block">
          <div className="eyebrow">SENTRA</div>
          <h1>Autonomous Data Center Console</h1>
          <p>
            Monitor, diagnose, and verify autonomous responses across the simulated
            micro data center.
          </p>
        </div>
        <div className="status-panel">
          <div className="status-pill">
            <span className={`dot ${error ? "dot-warn" : "dot-ok"}`} />
            <span>{connectionLabel}</span>
          </div>
          <div className="status-stack">
            <div className="status-item">
              <span>Tick</span>
              <strong>{displayState.tick}</strong>
            </div>
            <div className="status-item">
              <span>Incidents</span>
              <strong>{incidentCount}</strong>
            </div>
            <div className="status-item">
              <span>Last update</span>
              <strong>{lastUpdated ? lastUpdated.toLocaleTimeString() : "-"}</strong>
            </div>
          </div>
        </div>
      </header>

      {error && (
        <div className="alert">
          <strong>API issue:</strong> {error}
        </div>
      )}

      <main className="main-content">
        {route === "dashboard" && (
          <Dashboard
            state={displayState}
            events={events}
            incidentCount={incidentCount}
            onOpenEvents={(eventId) => {
              if (eventId) {
                window.location.hash = `/events?event=${eventId}`;
                return;
              }
              navigate("events");
            }}
          />
        )}
        {route === "fleet" && <ServerFleet state={displayState} />}
        {route === "events" && <EventTimeline events={events} />}
      </main>

      <ControlDrawer
        open={toolsOpen}
        onClose={() => setToolsOpen(false)}
        state={displayState}
        busy={busy}
        realtime={realtime}
        onAdvanceTick={advanceTick}
        onToggleAutonomy={toggleAutonomy}
        onInjectFault={injectFault}
        onReset={handleReset}
        onSetRealtime={setRealtime}
      />

      <DockNav
        active={route}
        onNavigate={navigate}
        toolsOpen={toolsOpen}
        onToggleTools={() => setToolsOpen((current) => !current)}
        themeMode={themeMode}
        onThemeModeChange={setThemeMode}
      />

      <NotificationTray
        items={notifications}
        onSelect={(item) => {
          setNotifications((current) =>
            current.filter((entry) => entry.id !== item.id)
          );
          navigate("events");
        }}
        onDismiss={(item) => {
          setNotifications((current) =>
            current.filter((entry) => entry.id !== item.id)
          );
        }}
      />
    </div>
  );
}
