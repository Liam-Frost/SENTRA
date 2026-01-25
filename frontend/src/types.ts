export type ServerId = "S1" | "S2" | "S3";

export type ServerStatus =
  | "running"
  | "booting"
  | "restarting"
  | "thermal_shutdown"
  | "off";

export type FaultType = "overheat" | "hardware_fail" | "network_spike";

export type EventType =
  | "fault"
  | "incident"
  | "action"
  | "ai"
  | "autonomy"
  | "reset";

export type MetricType = "temp" | "error_rate" | "health" | "load";

export type ActionType =
  | "reroute"
  | "throttle"
  | "enableCooling"
  | "disableCooling"
  | "restart";

export interface ServerState {
  load: number;
  temp: number;
  error_rate: number;
  power: number;
  health: number;
  cooling: boolean;
  cooling_level: number;
  status: ServerStatus;
}

export interface WorldState {
  tick: number;
  incoming_traffic: number;
  servers: Record<ServerId, ServerState>;
  autonomy_enabled: boolean;
}

export interface FaultPayload {
  type: FaultType;
  target: ServerId;
}

export interface IncidentPayload {
  target: ServerId;
  metric: MetricType;
  value: number;
  threshold: number;
  status?: "start" | "resolved";
}

export interface ActionPayload {
  action: ActionType;
  target?: ServerId;
}

export interface AiPayload {
  root_causes: string[];
  recommended_actions: string[];
  risks: string[];
  rollback_conditions: string[];
}

export interface AutonomyPayload {
  enabled: boolean;
}

export interface ResetPayload {
  reset_events: boolean;
}

export type EventPayload =
  | FaultPayload
  | IncidentPayload
  | ActionPayload
  | AiPayload
  | AutonomyPayload
  | ResetPayload
  | Record<string, unknown>;

export interface EventRecord {
  id: number;
  tick: number;
  ts: string;
  type: EventType;
  message: string;
  payload: EventPayload | null;
}

export interface EventsResponse {
  events: EventRecord[];
}
