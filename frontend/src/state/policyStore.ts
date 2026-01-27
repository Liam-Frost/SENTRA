import { useSyncExternalStore } from "react";

import {
  createPolicyApi,
  deletePolicyApi,
  listPolicies,
  updatePolicyApi
} from "../api/policies";
import { getSnapshot as getActionSnapshot } from "./actionStore";

export type PolicyMode = "ADVISE_ONLY" | "AUTO_EXECUTE";
export type PolicyStatus = "draft" | "active" | "archived";
export type ConditionOp = ">" | ">=" | "<" | "<=";
export type ConditionMetric = "temp" | "load" | "error_rate" | "health";
export type ConditionGroupOp = "AND" | "OR";
export type ActionCapability = "simulation" | "probe" | "both";
export type ActionAvailability = "available" | "future" | "deprecated";

export type ActionType =
  | "enableCooling"
  | "disableCooling"
  | "reroute"
  | "throttle"
  | "restart"
  | "maintenance_on"
  | "maintenance_off"
  | "restart_service"
  | "restart_host"
  | "run_script";

export type RiskLevel = 0 | 1 | 2 | 3;

export type Condition = {
  metric: ConditionMetric;
  op: ConditionOp;
  value: number;
  durationSec?: number;
};

export type ActionStep = {
  type: ActionType;
  params?: Record<string, unknown>;
  capability: ActionCapability;
  availability: ActionAvailability;
};

export type Policy = {
  id: string;
  name: string;
  description?: string;
  notes?: string;

  version: number;
  status: PolicyStatus;

  enabled: boolean;
  mode: PolicyMode;
  priority: number;

  scope: {
    type: "all" | "nodes" | "tag" | "group";
    selector?: { key: string; values: string[] };
    nodeIds?: string[];
  };

  conditions: {
    op: ConditionGroupOp;
    items: Condition[];
  };

  actions: ActionStep[];

  guardrails: {
    cooldownSec: number;
    maxPerHour: number;
    requireApproval: boolean;
  };

  createdAt: number;
  updatedAt: number;
  createdBy?: string;
  updatedBy?: string;

  riskLevel: RiskLevel;
};

export type ActionCatalogItem = {
  type: ActionType;
  label: string;
  capability: ActionCapability;
  availability: ActionAvailability;
  riskLevel: RiskLevel;
  description?: string;
};

export function getActionCatalogItem(type: ActionType): ActionCatalogItem | null {
  const actionStore = getActionSnapshot();
  const action = actionStore.actions.find((a) => a.id === type);
  
  if (!action) return null;
  
  return {
    type: action.id as ActionType,
    label: action.label,
    capability: action.capability,
    availability: action.availability,
    riskLevel: action.riskLevel as RiskLevel,
    description: action.description,
  };
}

export function getAvailableActions(): ActionCatalogItem[] {
  const actionStore = getActionSnapshot();
  return actionStore.actions
    .filter((a) => a.availability === "available")
    .map((action) => ({
      type: action.id as ActionType,
      label: action.label,
      capability: action.capability,
      availability: action.availability,
      riskLevel: action.riskLevel as RiskLevel,
      description: action.description,
    }));
}

export function computeRiskLevel(actions: ActionStep[]): RiskLevel {
  let maxRisk: RiskLevel = 0;
  for (const step of actions) {
    const catalog = getActionCatalogItem(step.type);
    const risk = catalog ? catalog.riskLevel : 3;
    if (risk > maxRisk) maxRisk = risk;
  }
  return maxRisk;
}

export function deriveRequireApproval(_mode: PolicyMode, _riskLevel: RiskLevel) {
  return false;
}

export function validatePolicy(policy: Policy): string[] {
  const errors: string[] = [];

  if (!policy.name.trim()) errors.push("name is required");
  if (!Number.isFinite(policy.priority)) errors.push("priority must be a number");
  if (policy.scope.type === "nodes") {
    const ids = policy.scope.nodeIds ?? [];
    if (ids.length === 0) errors.push("scope requires at least one node id");
  }

  if (policy.status === "active") {
    if (policy.conditions.items.length === 0) errors.push("active policy needs conditions");
    if (policy.actions.length === 0) errors.push("active policy needs at least one action");
  }

  return errors;
}

type StoreState = {
  policies: Policy[];
};

const STORAGE_KEY = "sentra-policies:v1";

let store: StoreState = loadStore();
const listeners = new Set<() => void>();
let idCounter = 0;

let backendHydrated = false;

function nextId(prefix: string) {
  idCounter += 1;
  return `${prefix}-${Date.now()}-${idCounter}`;
}

function loadStore(): StoreState {
  if (typeof window === "undefined") return { policies: [] };
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return { policies: [] };
  try {
    const parsed = JSON.parse(raw) as { policies?: Policy[] };
    const policies = Array.isArray(parsed.policies) ? parsed.policies : [];
    return { policies };
  } catch {
    return { policies: [] };
  }
}

function persist() {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

function emit() {
  listeners.forEach((listener) => listener());
}

function setStore(next: StoreState) {
  store = next;
  persist();
  emit();
}

export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSnapshot() {
  return store;
}

export function usePolicyStore() {
  return useSyncExternalStore(subscribe, getSnapshot);
}

export async function refreshPoliciesFromBackend() {
  if (typeof window === "undefined") return;
  if (backendHydrated) return;
  backendHydrated = true;
  try {
    const data = await listPolicies();
    if (!data || !Array.isArray(data.policies)) return;
    setStore({ policies: data.policies });
  } catch {
    // backend optional; keep local cache
  }
}

export async function createPolicy(seed?: Partial<Policy>) {
  const now = Date.now();
  const id = nextId("pol");
  const actions = seed?.actions ?? [];
  const riskLevel = computeRiskLevel(actions);
  const mode = seed?.mode ?? "ADVISE_ONLY";
  const requireApproval = seed?.guardrails?.requireApproval ?? false;

  const policy: Policy = {
    id,
    name: seed?.name ?? "New policy",
    description: seed?.description,
    notes: seed?.notes,
    version: 1,
    status: seed?.status ?? "draft",
    enabled: seed?.enabled ?? false,
    mode,
    priority: seed?.priority ?? 100,
    scope: seed?.scope ?? { type: "all" },
    conditions: seed?.conditions ?? { op: "AND", items: [] },
    actions,
    guardrails: seed?.guardrails ?? {
      cooldownSec: 60,
      maxPerHour: 12,
      requireApproval
    },
    createdAt: now,
    updatedAt: now,
    createdBy: seed?.createdBy,
    updatedBy: seed?.updatedBy,
    riskLevel
  };

  setStore({ policies: [policy, ...store.policies] });

  try {
    const created = await createPolicyApi(policy);
    if (created && created.policy && created.policy.id === policy.id) {
      const merged = [
        created.policy,
        ...store.policies.filter((existing) => existing.id !== policy.id)
      ];
      setStore({ policies: merged });
      return created.policy;
    }
  } catch {
    // keep local cache if backend unavailable
  }

  return policy;
}

export async function savePolicy(updated: Policy, updatedBy?: string) {
  const now = Date.now();
  const riskLevel = computeRiskLevel(updated.actions);

  const nextPolicy: Policy = {
    ...updated,
    version: updated.version + 1,
    updatedAt: now,
    updatedBy: updatedBy ?? updated.updatedBy,
    riskLevel,
    guardrails: {
      ...updated.guardrails,
      requireApproval: updated.guardrails.requireApproval
    }
  };

  const policies = store.policies.map((policy) =>
    policy.id === updated.id ? nextPolicy : policy
  );
  setStore({ policies });

  try {
    const saved = await updatePolicyApi(updated.id, nextPolicy);
    if (saved && saved.policy && saved.policy.id === updated.id) {
      setStore({
        policies: store.policies.map((policy) =>
          policy.id === updated.id ? saved.policy : policy
        )
      });
      return saved.policy;
    }
  } catch {
    // keep local cache if backend unavailable
  }

  return nextPolicy;
}

export async function patchPolicy(id: string, patch: Partial<Policy>) {
  const existing = store.policies.find((policy) => policy.id === id);
  if (!existing) return null;
  return savePolicy({ ...existing, ...patch });
}

export async function deletePolicy(id: string) {
  setStore({ policies: store.policies.filter((policy) => policy.id !== id) });
  try {
    await deletePolicyApi(id);
  } catch {
    // keep local cache if backend unavailable
  }
}

export async function duplicatePolicy(id: string) {
  const existing = store.policies.find((policy) => policy.id === id);
  if (!existing) return null;
  return createPolicy({
    ...existing,
    name: `${existing.name} (copy)`,
    enabled: false,
    status: "draft",
    version: 1,
    createdAt: Date.now(),
    updatedAt: Date.now()
  });
}

export async function createDraftPolicyFromIncident(input: {
  target: string;
  metric: ConditionMetric;
  threshold: number;
  incidentEventId: number;
  message: string;
}) {
  const metric = input.metric;
  const isHealth = metric === "health";
  const op: ConditionOp = isHealth ? "<" : ">";

  const actionTypes: ActionType[] = (() => {
    if (metric === "temp") return ["enableCooling", "throttle", "reroute"];
    if (metric === "load") return ["reroute", "throttle"];
    if (metric === "error_rate") return ["restart"];
    if (metric === "health") return ["restart"];
    return ["enableCooling"];
  })();

  const actions: ActionStep[] = actionTypes.map((type) => {
    const catalog = getActionCatalogItem(type);
    return {
      type,
      capability: catalog?.capability ?? "simulation",
      availability: catalog?.availability ?? "available"
    };
  });

  return createPolicy({
    name: `Draft: ${metricLabels(metric)} on ${input.target}`,
    notes: `from incident ${input.incidentEventId}: ${input.message}`,
    enabled: false,
    mode: "ADVISE_ONLY",
    status: "draft",
    scope: { type: "nodes", nodeIds: [input.target] },
    conditions: {
      op: "AND",
      items: [
        {
          metric,
          op,
          value: input.threshold,
          durationSec: 60
        }
      ]
    },
    actions
  });
}

export async function createDraftPolicyForNode(nodeId: string) {
  return createPolicy({
    name: `Draft: node ${nodeId}`,
    enabled: false,
    mode: "ADVISE_ONLY",
    status: "draft",
    scope: { type: "nodes", nodeIds: [nodeId] },
    conditions: {
      op: "AND",
      items: []
    },
    actions: []
  });
}

function metricLabels(metric: ConditionMetric) {
  if (metric === "temp") return "Temp";
  if (metric === "load") return "CPU";
  if (metric === "error_rate") return "Error";
  if (metric === "health") return "Health";
  return metric;
}

if (typeof window !== "undefined") {
  void refreshPoliciesFromBackend();
}
