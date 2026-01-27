import { request } from "./client";

export type OperationStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "partial"
  | "cancelled";

export type ApprovalState = "none" | "pending" | "approved" | "rejected";

export type Operation = {
  id: string;
  actionType: string;
  status: OperationStatus;
  approvalState: ApprovalState;
  mode: string;
  targets: string[];
  parameters?: Record<string, unknown> | null;
  initiator: string;
  policyId?: string | null;
  policyVersion?: number | null;
  policyName?: string | null;
  createdAt: number;
  updatedAt: number;
};

export type OperationRun = {
  id: number;
  operationId: string;
  nodeId: string | null;
  status: "queued" | "running" | "succeeded" | "failed";
  startedAt?: number | null;
  finishedAt?: number | null;
  output?: string | null;
  exitCode?: number | null;
};

export async function listOperations(params: {
  status?: OperationStatus | "all";
  limit?: number;
} = {}): Promise<{ operations: Operation[] }> {
  const query = new URLSearchParams();
  if (params.status && params.status !== "all") query.set("status", params.status);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return request<{ operations: Operation[] }>(
    qs ? `/api/operations?${qs}` : "/api/operations"
  );
}

export async function getOperation(id: string): Promise<{ operation: Operation; runs: OperationRun[] }> {
  return request<{ operation: Operation; runs: OperationRun[] }>(
    `/api/operations/${encodeURIComponent(id)}`
  );
}

export async function createOperation(input: {
  action: string;
  targets: string[];
  parameters?: Record<string, unknown>;
  initiator?: string;
  approval_state?: ApprovalState;
}): Promise<{ operation: Operation }> {
  return request<{ operation: Operation }>("/api/operations", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function deleteOperation(id: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/operations/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}
