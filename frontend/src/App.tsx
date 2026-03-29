import { useEffect, useMemo, useRef, useState } from "react";
import DockNav, { type RouteKey } from "./components/DockNav";
import ControlDrawer from "./components/ControlDrawer";
import NotificationTray, { type NotificationItem } from "./components/NotificationTray";
import SideNav from "./components/SideNav";
import TopBar from "./components/TopBar";
import type { ServerState, WorldState } from "./types";
import { useSentra } from "./state/useSentra";
import Dashboard from "./pages/Dashboard";
import ServerFleet from "./pages/ServerFleet";
import EventTimeline from "./pages/EventTimeline";
import IncidentsPage from "./pages/Incidents";
import PoliciesPage from "./pages/Policies";
import OperationsPage from "./pages/Operations";
import ProjectsPage from "./pages/Projects";
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

const simulationRoutes: RouteKey[] = [
  "dashboard",
  "fleet",
  "incidents",
  "projects",
  "policies",
  "operations",
  "events"
];

const nonSimulationRoutes: RouteKey[] = [
  "dashboard",
  "fleet",
  "incidents",
  "projects",
  "operations",
  "policies",
  "events"
];

function parseRoute(allowedRoutes: RouteKey[], fallbackRoute: RouteKey): RouteKey {
  const raw = window.location.hash.replace("#/", "").replace("#", "");
  const routeKey = raw.split("?")[0];
  if (allowedRoutes.includes(routeKey as RouteKey)) return routeKey as RouteKey;
  return fallbackRoute;
}

function useHashRoute(allowedRoutes: RouteKey[], fallbackRoute: RouteKey) {
  const [route, setRoute] = useState<RouteKey>(() => parseRoute(allowedRoutes, fallbackRoute));

  useEffect(() => {
    const handler = () => setRoute(parseRoute(allowedRoutes, fallbackRoute));
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, [allowedRoutes, fallbackRoute]);

  useEffect(() => {
    const next = parseRoute(allowedRoutes, fallbackRoute);
    if (next !== route) {
      setRoute(next);
    }
  }, [allowedRoutes, fallbackRoute, route]);

  const navigate = (next: RouteKey) => {
    if (!allowedRoutes.includes(next)) {
      window.location.hash = `/${fallbackRoute}`;
      return;
    }
    window.location.hash = `/${next}`;
  };

  return { route, navigate };
}

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    const media = window.matchMedia(query);
    const handler = () => setMatches(media.matches);
    handler();

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
  }, [query]);

  return matches;
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
    simulationEnabled,
    capabilitiesLoading,
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

  const visibleRoutes = useMemo(
    () => (simulationEnabled ? simulationRoutes : nonSimulationRoutes),
    [simulationEnabled]
  );
  const fallbackRoute: RouteKey = "dashboard";

  const displayState = state ?? fallbackState;
  const incidentCount = useMemo(() => {
    return events.filter((event) => event.type === "incident").length;
  }, [events]);

  const { route, navigate } = useHashRoute(visibleRoutes, fallbackRoute);
  const [toolsOpen, setToolsOpen] = useState(false);
  const useSideNav = useMediaQuery("(min-width: 1280px)");
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null;
    return stored ?? "system";
  });

  const [notifications, setNotifications] = useState<
    (NotificationItem & { expiresAt: number })[]
  >([]);
  const lastIncidentIdRef = useRef(0);

  useEffect(() => {
    if (capabilitiesLoading) return;
    if (!window.location.hash) {
      window.location.hash = `/${fallbackRoute}`;
    }
  }, [capabilitiesLoading, fallbackRoute]);

  useEffect(() => {
    if (!simulationEnabled) {
      setToolsOpen(false);
      return;
    }
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
  }, [simulationEnabled]);

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

  const connectionLabel =
    capabilitiesLoading || loading ? "Connecting" : error ? "Degraded" : "Live";
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
      <div className={`app-layout ${useSideNav ? "has-side-nav" : ""}`.trim()}>
        {useSideNav ? (
          <SideNav
            active={route}
            onNavigate={navigate}
            toolsOpen={toolsOpen}
            onToggleTools={() => setToolsOpen((current) => !current)}
            simulationEnabled={simulationEnabled}
            themeMode={themeMode}
            onThemeModeChange={setThemeMode}
          />
        ) : null}

        <div className="app-body">
          <TopBar
            route={route}
            connectionLabel={connectionLabel}
            hasError={Boolean(error)}
            tick={displayState.tick}
            incidentCount={incidentCount}
            autonomyEnabled={displayState.autonomy_enabled}
            simulationEnabled={simulationEnabled}
            lastUpdated={lastUpdated}
            themeMode={themeMode}
          />

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
                  simulationEnabled={simulationEnabled}
                  lastUpdated={lastUpdated}
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
            {route === "incidents" && (
              <IncidentsPage state={displayState} events={events} />
            )}
            {route === "projects" && <ProjectsPage />}
            {route === "policies" && <PoliciesPage />}
            {route === "operations" && <OperationsPage />}
            {route === "events" && <EventTimeline events={events} />}
          </main>
        </div>
      </div>

      {simulationEnabled ? (
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
      ) : null}

      {useSideNav ? null : (
        <DockNav
          active={route}
          onNavigate={navigate}
          toolsOpen={toolsOpen}
          onToggleTools={() => setToolsOpen((current) => !current)}
          simulationEnabled={simulationEnabled}
          themeMode={themeMode}
          onThemeModeChange={setThemeMode}
        />
      )}

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
