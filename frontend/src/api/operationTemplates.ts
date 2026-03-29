import { request } from "./client";
import type { OperationLog, OperationRun, OperationStatus } from "./operations";

export type OperationTemplateStep = {
  id?: number;
  position: number;
  name: string;
  command: string;
  timeoutSec: number;
  continueOnError: boolean;
};

export type OperationTemplate = {
  id: string;
  name: string;
  description?: string | null;
  steps: OperationTemplateStep[];
  createdAt: number;
  updatedAt: number;
};

export type OperationExecution = {
  id: string;
  templateId?: string | null;
  templateName?: string | null;
  source?: string | null;
  status: OperationStatus;
  targets: string[];
  initiator: string;
  createdAt: number;
  updatedAt: number;
  parameters?: Record<string, unknown> | null;
};

export type OperationExecutionDetail = {
  execution: OperationExecution & {
    actionType?: string;
    approvalState?: string;
    mode?: string;
  };
  runs: OperationRun[];
  logs: OperationLog[];
};

export async function listOperationTemplates(): Promise<{ templates: OperationTemplate[] }> {
  return request<{ templates: OperationTemplate[] }>("/api/operation-templates");
}

export async function createOperationTemplate(input: {
  name: string;
  description?: string;
  steps: OperationTemplateStep[];
}): Promise<{ template: OperationTemplate }> {
  return request<{ template: OperationTemplate }>("/api/operation-templates", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function updateOperationTemplate(
  id: string,
  input: {
    name: string;
    description?: string;
    steps: OperationTemplateStep[];
  }
): Promise<{ template: OperationTemplate }> {
  return request<{ template: OperationTemplate }>(`/api/operation-templates/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(input)
  });
}

export async function deleteOperationTemplate(id: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/operation-templates/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export async function executeOperationTemplate(
  id: string,
  input: { targets: string[]; initiator?: string }
): Promise<{ execution: OperationExecution }> {
  return request<{ execution: OperationExecution }>(
    `/api/operation-templates/${encodeURIComponent(id)}/execute`,
    {
      method: "POST",
      body: JSON.stringify(input)
    }
  );
}

export async function listOperationExecutions(params: {
  templateId?: string;
  source?: string;
  limit?: number;
} = {}): Promise<{ executions: OperationExecution[] }> {
  const query = new URLSearchParams();
  if (params.templateId) query.set("template_id", params.templateId);
  if (params.source) query.set("source", params.source);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  const qs = query.toString();
  return request<{ executions: OperationExecution[] }>(
    qs ? `/api/operation-executions?${qs}` : "/api/operation-executions"
  );
}

export async function getOperationExecution(id: string): Promise<OperationExecutionDetail> {
  return request<OperationExecutionDetail>(`/api/operation-executions/${encodeURIComponent(id)}`);
}
