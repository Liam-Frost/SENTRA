import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EventRecord, FaultType, ServerId, WorldState } from "../types";
import {
  getEvents,
  getState,
  injectFault,
  resetWorld,
  setAutonomy,
  tick
} from "../api/sentra";

const STATE_POLL_MS = 1500;
const EVENTS_POLL_MS = 2500;
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
  state: WorldState | null;
  events: EventRecord[];
  loading: boolean;
  error: string | null;
  busy: boolean;
  lastUpdated: Date | null;
  refresh: () => Promise<void>;
  advanceTick: (steps?: number) => Promise<void>;
  toggleAutonomy: (enabled: boolean) => Promise<void>;
  injectFault: (type: FaultType, target: ServerId) => Promise<void>;
  reset: (resetEvents: boolean) => Promise<void>;
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
  const [state, setState] = useState<WorldState | null>(null);
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

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
      // Use limit only; merge handles dedup. sinceTick is best-effort optimization.
      const data = await getEvents({ limit: 200 });
      if (!mounted.current) return;
      setEvents((current) => mergeEvents(current, data.events));
      setError(null);
    } catch (err) {
      if (!mounted.current) return;
      const message = err instanceof Error ? err.message : "Failed to load events";
      setError(message);
    }
  }, [mounted]);

  const refresh = useCallback(async () => {
    await Promise.all([refreshState(), refreshEvents()]);
  }, [refreshEvents, refreshState]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const interval = window.setInterval(refreshState, STATE_POLL_MS);
    return () => window.clearInterval(interval);
  }, [refreshState]);

  useEffect(() => {
    const interval = window.setInterval(refreshEvents, EVENTS_POLL_MS);
    return () => window.clearInterval(interval);
  }, [refreshEvents]);

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
      await runAction(async () => {
        const data = await tick(steps);
        setState(data);
        await refreshEvents();
      });
    },
    [refreshEvents, runAction]
  );

  const toggleAutonomy = useCallback(
    async (enabled: boolean) => {
      await runAction(async () => {
        await setAutonomy(enabled);
        await refresh();
      });
    },
    [refresh, runAction]
  );

  const injectFaultAction = useCallback(
    async (type: FaultType, target: ServerId) => {
      await runAction(async () => {
        await injectFault({ type, target });
        await refresh();
      });
    },
    [refresh, runAction]
  );

  const reset = useCallback(
    async (resetEvents: boolean) => {
      await runAction(async () => {
        const data = await resetWorld(resetEvents);
        setState(data);
        if (resetEvents) {
          setEvents([]);
          return;
        }
        await refreshEvents();
      });
    },
    [refreshEvents, runAction]
  );

  const result = useMemo(
    () => ({
      state,
      events,
      loading,
      error,
      busy,
      lastUpdated,
      refresh,
      advanceTick,
      toggleAutonomy,
      injectFault: injectFaultAction,
      reset
    }),
    [
      advanceTick,
      busy,
      error,
      events,
      injectFaultAction,
      lastUpdated,
      loading,
      refresh,
      reset,
      state,
      toggleAutonomy
    ]
  );

  return result;
}
