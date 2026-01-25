import { request } from "./client";
import type {
  EventsResponse,
  FaultType,
  ServerId,
  WorldState
} from "../types";

type TickRequest = {
  steps?: number;
};

type FaultRequest = {
  type: FaultType;
  target: ServerId;
};

type AutonomyRequest = {
  enabled: boolean;
};

type ResetRequest = {
  reset_events?: boolean;
};

export async function getState(): Promise<WorldState> {
  return request<WorldState>("/api/state");
}

export async function tick(steps?: number): Promise<WorldState> {
  const body: TickRequest = steps !== undefined ? { steps } : {};
  return request<WorldState>("/api/tick", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export async function injectFault(payload: FaultRequest): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>("/api/fault", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

type EventsQuery = {
  limit?: number;
  sinceTick?: number;
  type?: string[];
  target?: string[];
};

export async function getEvents(params: EventsQuery = {}): Promise<EventsResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.sinceTick !== undefined) query.set("since_tick", String(params.sinceTick));
  if (params.type && params.type.length > 0) query.set("type", params.type.join(","));
  if (params.target && params.target.length > 0) query.set("target", params.target.join(","));

  const qs = query.toString();
  return request<EventsResponse>(qs ? `/api/events?${qs}` : "/api/events");
}

export async function setAutonomy(enabled: boolean): Promise<{ enabled: boolean }> {
  const body: AutonomyRequest = { enabled };
  return request<{ enabled: boolean }>("/api/autonomy", {
    method: "POST",
    body: JSON.stringify(body)
  });
}

export async function resetWorld(resetEvents = true): Promise<WorldState> {
  const body: ResetRequest = { reset_events: resetEvents };
  return request<WorldState>("/api/reset", {
    method: "POST",
    body: JSON.stringify(body)
  });
}
