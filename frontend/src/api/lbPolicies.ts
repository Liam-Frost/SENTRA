import { request } from "./client";

export type LbPolicyAllocation = {
  id?: number;
  nodeId: string;
  weight: number;
  enabled: boolean;
  priority: number;
};

export type LbPolicy = {
  id: string;
  projectId: string;
  name: string;
  description?: string | null;
  status: "draft" | "active";
  drMode: "manual" | "active-standby" | "weighted-failover";
  healthCheckPath?: string | null;
  healthCheckIntervalSec: number;
  failureThreshold: number;
  recoveryThreshold: number;
  autoFailback: boolean;
  allocations: LbPolicyAllocation[];
  createdAt: number;
  updatedAt: number;
};

export async function listLbPolicies(params: { projectId?: string } = {}): Promise<{ policies: LbPolicy[] }> {
  const query = new URLSearchParams();
  if (params.projectId) query.set("project_id", params.projectId);
  const qs = query.toString();
  return request<{ policies: LbPolicy[] }>(qs ? `/api/lb-policies?${qs}` : "/api/lb-policies");
}

export async function createLbPolicy(input: {
  projectId: string;
  name: string;
  description?: string;
  status: "draft" | "active";
  drMode: "manual" | "active-standby" | "weighted-failover";
  healthCheckPath?: string;
  healthCheckIntervalSec: number;
  failureThreshold: number;
  recoveryThreshold: number;
  autoFailback: boolean;
  allocations: LbPolicyAllocation[];
}): Promise<{ policy: LbPolicy }> {
  return request<{ policy: LbPolicy }>("/api/lb-policies", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function updateLbPolicy(
  id: string,
  input: {
    projectId: string;
    name: string;
    description?: string;
    status: "draft" | "active";
    drMode: "manual" | "active-standby" | "weighted-failover";
    healthCheckPath?: string;
    healthCheckIntervalSec: number;
    failureThreshold: number;
    recoveryThreshold: number;
    autoFailback: boolean;
    allocations: LbPolicyAllocation[];
  }
): Promise<{ policy: LbPolicy }> {
  return request<{ policy: LbPolicy }>(`/api/lb-policies/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(input)
  });
}

export async function deleteLbPolicy(id: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/lb-policies/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export async function applyLbPolicy(
  id: string,
  initiator = "policy"
): Promise<{ policy: LbPolicy; execution: { id: string } }> {
  return request<{ policy: LbPolicy; execution: { id: string } }>(
    `/api/lb-policies/${encodeURIComponent(id)}/apply`,
    {
      method: "POST",
      body: JSON.stringify({ initiator })
    }
  );
}
