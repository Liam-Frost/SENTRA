const API_BASE = "/api";

export type Action = {
  id: string;
  label: string;
  category?: string;
  capability: "simulation" | "probe" | "both";
  availability: "available" | "future" | "deprecated";
  riskLevel: number;
  requiresTarget: boolean;
  description?: string;
  parametersSchema?: string;
  defaultParameters?: string;
  isSystem: boolean;
  createdAt: number;
  updatedAt: number;
};

export type ActionReferences = {
  policies: Array<{ id: string; name: string }>;
  operations: Array<{ id: string; actionType: string; status: string; createdAt: number }>;
};

export async function listActions(filters?: {
  availability?: string;
  capability?: string;
  category?: string;
}): Promise<{ actions: Action[] }> {
  const params = new URLSearchParams();
  if (filters?.availability) params.set("availability", filters.availability);
  if (filters?.capability) params.set("capability", filters.capability);
  if (filters?.category) params.set("category", filters.category);
  
  const query = params.toString();
  const url = `${API_BASE}/actions${query ? `?${query}` : ""}`;
  
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Failed to list actions: ${resp.statusText}`);
  }
  
  const data = await resp.json();
  return {
    actions: data.actions.map((a: any) => ({
      ...a,
      riskLevel: a.risk_level,
      requiresTarget: a.requires_target,
      parametersSchema: a.parameters_schema,
      defaultParameters: a.default_parameters,
      isSystem: a.is_system,
      createdAt: a.created_at,
      updatedAt: a.updated_at,
    })),
  };
}

export async function getAction(id: string): Promise<{ action: Action }> {
  const resp = await fetch(`${API_BASE}/actions/${encodeURIComponent(id)}`);
  if (!resp.ok) {
    throw new Error(`Failed to get action: ${resp.statusText}`);
  }
  
  const data = await resp.json();
  return {
    action: {
      ...data.action,
      riskLevel: data.action.risk_level,
      requiresTarget: data.action.requires_target,
      parametersSchema: data.action.parameters_schema,
      defaultParameters: data.action.default_parameters,
      isSystem: data.action.is_system,
      createdAt: data.action.created_at,
      updatedAt: data.action.updated_at,
    },
  };
}

export async function createAction(data: Partial<Action>): Promise<{ action: Action }> {
  const payload = {
    id: data.id,
    label: data.label,
    category: data.category,
    capability: data.capability,
    availability: data.availability,
    risk_level: data.riskLevel,
    requires_target: data.requiresTarget,
    description: data.description,
    parameters_schema: data.parametersSchema,
    default_parameters: data.defaultParameters,
  };
  
  const resp = await fetch(`${API_BASE}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ error: { message: resp.statusText } }));
    throw new Error(error.error?.message || "Failed to create action");
  }
  
  const result = await resp.json();
  return {
    action: {
      ...result.action,
      riskLevel: result.action.risk_level,
      requiresTarget: result.action.requires_target,
      parametersSchema: result.action.parameters_schema,
      defaultParameters: result.action.default_parameters,
      isSystem: result.action.is_system,
      createdAt: result.action.created_at,
      updatedAt: result.action.updated_at,
    },
  };
}

export async function updateAction(
  id: string,
  data: Partial<Action>
): Promise<{ action: Action }> {
  const payload: any = {};
  if (data.label !== undefined) payload.label = data.label;
  if (data.category !== undefined) payload.category = data.category;
  if (data.capability !== undefined) payload.capability = data.capability;
  if (data.availability !== undefined) payload.availability = data.availability;
  if (data.riskLevel !== undefined) payload.risk_level = data.riskLevel;
  if (data.requiresTarget !== undefined) payload.requires_target = data.requiresTarget;
  if (data.description !== undefined) payload.description = data.description;
  if (data.parametersSchema !== undefined) payload.parameters_schema = data.parametersSchema;
  if (data.defaultParameters !== undefined) payload.default_parameters = data.defaultParameters;
  
  const resp = await fetch(`${API_BASE}/actions/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ error: { message: resp.statusText } }));
    throw new Error(error.error?.message || "Failed to update action");
  }
  
  const result = await resp.json();
  return {
    action: {
      ...result.action,
      riskLevel: result.action.risk_level,
      requiresTarget: result.action.requires_target,
      parametersSchema: result.action.parameters_schema,
      defaultParameters: result.action.default_parameters,
      isSystem: result.action.is_system,
      createdAt: result.action.created_at,
      updatedAt: result.action.updated_at,
    },
  };
}

export async function deleteAction(id: string): Promise<{ ok: boolean }> {
  const resp = await fetch(`${API_BASE}/actions/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ error: { message: resp.statusText } }));
    throw new Error(error.error?.message || "Failed to delete action");
  }
  
  const result = await resp.json();
  return { ok: result.ok };
}

export async function getActionReferences(id: string): Promise<ActionReferences> {
  const resp = await fetch(`${API_BASE}/actions/${encodeURIComponent(id)}/references`);
  if (!resp.ok) {
    throw new Error(`Failed to get action references: ${resp.statusText}`);
  }
  
  const data = await resp.json();
  return data;
}

export async function executeActions(
  actions: string[],
  targets: string[],
  initiator: string = "manual"
): Promise<{ operations: string[] }> {
  const resp = await fetch(`${API_BASE}/actions/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actions, targets, initiator }),
  });
  
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ error: { message: resp.statusText } }));
    throw new Error(error.error?.message || "Failed to execute actions");
  }
  
  const result = await resp.json();
  return { operations: result.operations };
}
