import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EventRecord, FaultType, ServerId, WorldState } from "../types";
import {
  getCapabilities,
  getEvents,
  getRealtime,
  getState,
  injectFault,
  resetWorld,
  setAutonomy,
  setRealtime,
  tick
} from "../api/sentra";
import type { RealtimeState } from "../api/sentra";

const STATE_POLL_MS = 1500;
const EVENTS_POLL_MS = 2500;
const REALTIME_POLL_MS = 3000;
const EVENT_BUFFER_LIMIT = 500;

function useMountedRef() {
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  return mounted;
}

type UseSentraResult = {
  simulationEnabled: boolean;
  capabilitiesLoading: boolean;
  state: WorldState | null;
  events: EventRecord[];
  loading: boolean;
  error: string | null;
  busy: boolean;
  lastUpdated: Date | null;
  realtime: RealtimeState;
  refresh: () => Promise<void>;
  advanceTick: (steps?: number) => Promise<void>;
  toggleAutonomy: (enabled: boolean) => Promise<void>;
  injectFault: (type: FaultType, target: ServerId) => Promise<void>;
  reset: (resetEvents: boolean) => Promise<void>;
  setRealtime: (enabled: boolean, hz?: number) => Promise<void>;
};

function mergeEvents(existing: EventRecord[], incoming: EventRecord[]) {
  const byId = new Map<number, EventRecord>();
  for (const event of existing) {
    byId.set(event.id, event);
  }
  for (const event of incoming) {
    byId.set(event.id, event);
  }
  const merged = Array.from(byId.values()).sort((a, b) => a.id - b.id);
  if (merged.length > EVENT_BUFFER_LIMIT) {
    return merged.slice(-EVENT_BUFFER_LIMIT);
  }
  return merged;
}

export function useSentra(): UseSentraResult {
  const mounted = useMountedRef();
  const [simulationEnabled, setSimulationEnabled] = useState(false);
  const [capabilitiesLoading, setCapabilitiesLoading] = useState(true);
  const [state, setState] = useState<WorldState | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const maxEventIdRef = useRef(0);
  const [realtime, setRealtimeState] = useState<RealtimeState>({
    enabled: false,
    hz: 1
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadCapabilities = async () => {
      try {
        const data = await getCapabilities();
        if (cancelled || !mounted.current) return;
        setSimulationEnabled(Boolean(data.simulation_enabled));
        setError(null);
      } catch (err) {
        if (cancelled || !mounted.current) return;
        const message = err instanceof Error ? err.message : "Failed to load capabilities";
        setError(message);
      } finally {
        if (cancelled || !mounted.current) return;
        setCapabilitiesLoading(false);
      }
    };

    loadCapabilities();
    return () => {
      cancelled = true;
    };
  }, [mounted]);

  const refreshState = useCallback(async () => {
    try {
      const data = await getState();
      if (!mounted.current) return;
      setState(data);
      setError(null);
      setLastUpdated(new Date());
      setLoading(false);
    } catch (err) {
      if (!mounted.current) return;
      const message = err instanceof Error ? err.message : "Failed to load state";
      setError(message);
      setLoading(false);
    }
  }, [mounted]);

  const refreshEvents = useCallback(async () => {
    try {
      const afterId = maxEventIdRef.current > 0 ? maxEventIdRef.current : undefined;
      const data = await getEvents({ limit: 200, afterId });
      if (!mounted.current) return;
      setEvents((current) => {
        const merged = mergeEvents(current, data.events);
        maxEventIdRef.current = merged.length > 0 ? merged[merged.length - 1].id : 0;
        return merged;
      });
      setError(null);
    } catch (err) {
      if (!mounted.current) return;
      const message = err instanceof Error ? err.message : "Failed to load events";
      setError(message);
    }
  }, [mounted]);

  useEffect(() => {
    const interval = window.setInterval(refreshState, STATE_POLL_MS);
    return () => window.clearInterval(interval);
  }, [refreshState]);

  useEffect(() => {
    const interval = window.setInterval(refreshEvents, EVENTS_POLL_MS);
    return () => window.clearInterval(interval);
  }, [refreshEvents]);

  const refreshRealtime = useCallback(async () => {
    if (!simulationEnabled) {
      if (!mounted.current) return;
      setRealtimeState({ enabled: false, hz: 1 });
      return;
    }
    try {
      const data = await getRealtime();
      if (!mounted.current) return;
      setRealtimeState(data);
    } catch {
      if (!mounted.current) return;
    }
  }, [mounted, simulationEnabled]);

  const refresh = useCallback(async () => {
    if (capabilitiesLoading) return;
    setLoading(true);
    try {
      const jobs = [refreshEvents()];
      jobs.push(refreshState());
      if (simulationEnabled) jobs.push(refreshRealtime());
      await Promise.all(jobs);
    } finally {
      if (!mounted.current) return;
      setLoading(false);
    }
  }, [
    capabilitiesLoading,
    mounted,
    refreshEvents,
    refreshRealtime,
    refreshState,
    simulationEnabled
  ]);

  useEffect(() => {
    if (capabilitiesLoading) return;
    refresh();
  }, [capabilitiesLoading, refresh]);

  useEffect(() => {
    if (!simulationEnabled) return;
    const interval = window.setInterval(refreshRealtime, REALTIME_POLL_MS);
    return () => window.clearInterval(interval);
  }, [refreshRealtime, simulationEnabled]);

  const runAction = useCallback(
    async (action: () => Promise<void>) => {
      setBusy(true);
      try {
        await action();
      } catch (err) {
        const message = err instanceof Error ? err.message : "Action failed";
        setError(message);
      } finally {
        setBusy(false);
      }
    },
    []
  );

  const advanceTick = useCallback(
    async (steps?: number) => {
      if (!simulationEnabled) {
        setError("Simulation controls are disabled.");
        return;
      }
      await runAction(async () => {
        const data = await tick(steps);
        setState(data);
        await refreshEvents();
      });
    },
    [refreshEvents, runAction, simulationEnabled]
  );

  const toggleAutonomy = useCallback(
    async (enabled: boolean) => {
      if (!simulationEnabled) {
        setError("Simulation controls are disabled.");
        return;
      }
      await runAction(async () => {
        await setAutonomy(enabled);
        await refresh();
      });
    },
    [refresh, runAction, simulationEnabled]
  );

  const injectFaultAction = useCallback(
    async (type: FaultType, target: ServerId) => {
      if (!simulationEnabled) {
        setError("Simulation controls are disabled.");
        return;
      }
      await runAction(async () => {
        await injectFault({ type, target });
        await refresh();
      });
    },
    [refresh, runAction, simulationEnabled]
  );

  const reset = useCallback(
    async (resetEvents: boolean) => {
      if (!simulationEnabled) {
        setError("Simulation controls are disabled.");
        return;
      }
      await runAction(async () => {
        const data = await resetWorld(resetEvents);
        setState(data);
        if (resetEvents) {
          setEvents([]);
          maxEventIdRef.current = 0;
          return;
        }
        await refreshEvents();
      });
    },
    [refreshEvents, runAction, simulationEnabled]
  );

  const setRealtimeMode = useCallback(
    async (enabled: boolean, hz?: number) => {
      if (!simulationEnabled) {
        setError("Simulation controls are disabled.");
        return;
      }
      await runAction(async () => {
        const data = await setRealtime(enabled, hz);
        setRealtimeState(data);
      });
    },
    [runAction, simulationEnabled]
  );

  const result = useMemo(
    () => ({
      simulationEnabled,
      capabilitiesLoading,
      state,
      events,
      loading,
      error,
      busy,
      lastUpdated,
      realtime,
      refresh,
      advanceTick,
      toggleAutonomy,
      injectFault: injectFaultAction,
      reset,
      setRealtime: setRealtimeMode
    }),
    [
      advanceTick,
      busy,
      capabilitiesLoading,
      error,
      events,
      injectFaultAction,
      lastUpdated,
      loading,
      realtime,
      refresh,
      reset,
      simulationEnabled,
      setRealtimeMode,
      state,
      toggleAutonomy
    ]
  );

  return result;
}
