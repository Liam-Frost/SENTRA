import { request } from "./client";

import type { Policy } from "../state/policyStore";

export type PoliciesResponse = {
  policies: Policy[];
};

export type PolicyResponse = {
  policy: Policy;
  versions?: unknown;
};

export async function listPolicies(): Promise<PoliciesResponse> {
  return request<PoliciesResponse>("/api/policies");
}

export async function createPolicyApi(policy: Policy): Promise<PolicyResponse> {
  return request<PolicyResponse>("/api/policies", {
    method: "POST",
    body: JSON.stringify({ policy })
  });
}

export async function updatePolicyApi(id: string, policy: Policy): Promise<PolicyResponse> {
  return request<PolicyResponse>(`/api/policies/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify({ policy })
  });
}

export async function deletePolicyApi(id: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/policies/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export async function validatePolicyApi(policy: Policy): Promise<{ errors: string[] }> {
  return request<{ errors: string[] }>("/api/policies/validate", {
    method: "POST",
    body: JSON.stringify({ policy })
  });
}

export async function dryRunPolicyApi(policy: Policy): Promise<unknown> {
  return request<unknown>("/api/policies/dry-run", {
    method: "POST",
    body: JSON.stringify({ policy })
  });
}

export async function runPolicyApi(
  id: string,
  force = false
): Promise<{ operations: unknown[]; decisions: unknown[] }> {
  return request<{ operations: unknown[]; decisions: unknown[] }>(
    `/api/policies/${encodeURIComponent(id)}/run`,
    {
      method: "POST",
      body: JSON.stringify({ force })
    }
  );
}
