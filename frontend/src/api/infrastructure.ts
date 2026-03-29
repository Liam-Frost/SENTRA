import { request } from "./client";

export type NodeMetrics = {
  cpu: number;
  memory: number;
  disk: number;
  netIn: number;
  netOut: number;
  temp: number;
  errorRate: number;
  health: number;
  power: number;
  updatedAt?: number | null;
};

export type Node = {
  id: string;
  hostname: string;
  ip?: string | null;
  os?: string | null;
  arch?: string | null;
  status: string;
  agent?: {
    id?: string | null;
    version?: string | null;
    lastSeenAt?: number | null;
  } | null;
  metrics: NodeMetrics;
  createdAt?: number | null;
  updatedAt?: number | null;
};

export type DashboardSummary = {
  totalNodes: number;
  onlineNodes: number;
  offlineNodes: number;
  incidentNodes: number;
  avgCpu: number;
  avgMemory: number;
  avgDisk: number;
  projects: number;
  loadBalancers: number;
  policies: number;
  activePolicies: number;
  templates: number;
  executions: number;
  runningExecutions: number;
  queuedExecutions: number;
};

export type DashboardExecution = {
  status: string;
  createdAt: number;
  templateId?: string | null;
  templateName?: string | null;
  targetCount: number;
};

export type DashboardResponse = {
  summary: DashboardSummary;
  nodes: Node[];
  recentExecutions: DashboardExecution[];
};

export type Project = {
  id: string;
  name: string;
  description?: string | null;
  createdAt: number;
  updatedAt: number;
};

export type LoadBalancer = {
  id: string;
  projectId: string;
  nodeId: string;
  type: "nginx" | "haproxy" | "traefik";
  status: string;
  listenPort?: number | null;
  config?: Record<string, unknown>;
  createdAt: number;
  updatedAt: number;
};

export async function getDashboard(): Promise<DashboardResponse> {
  return request<DashboardResponse>("/api/dashboard");
}

export async function listNodes(): Promise<{ nodes: Node[] }> {
  return request<{ nodes: Node[] }>("/api/nodes");
}

export async function listProjects(): Promise<{ projects: Project[] }> {
  return request<{ projects: Project[] }>("/api/projects");
}

export async function createProject(input: {
  id?: string;
  name: string;
  description?: string;
}): Promise<{ project: Project }> {
  return request<{ project: Project }>("/api/projects", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function updateProject(
  id: string,
  input: { name?: string; description?: string }
): Promise<{ project: Project }> {
  return request<{ project: Project }>(`/api/projects/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(input)
  });
}

export async function deleteProject(id: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/projects/${encodeURIComponent(id)}`, {
    method: "DELETE"
  });
}

export async function listLoadBalancers(params: {
  projectId?: string;
  nodeId?: string;
} = {}): Promise<{ loadBalancers: LoadBalancer[] }> {
  const query = new URLSearchParams();
  if (params.projectId) query.set("project_id", params.projectId);
  if (params.nodeId) query.set("node_id", params.nodeId);
  const qs = query.toString();
  return request<{ loadBalancers: LoadBalancer[] }>(
    qs ? `/api/load-balancers?${qs}` : "/api/load-balancers"
  );
}

export async function createLoadBalancer(input: {
  projectId: string;
  nodeId: string;
  type: "nginx" | "haproxy" | "traefik";
  listenPort?: number;
  config?: Record<string, unknown>;
}): Promise<{ loadBalancer: LoadBalancer; operation: { id: string } }> {
  return request<{ loadBalancer: LoadBalancer; operation: { id: string } }>(
    "/api/load-balancers",
    {
      method: "POST",
      body: JSON.stringify(input)
    }
  );
}

export async function createLoadBalancersBatch(input: {
  projectId: string;
  nodeIds: string[];
  type: "nginx" | "haproxy" | "traefik";
  listenPort?: number;
  config?: Record<string, unknown>;
}): Promise<{ loadBalancers: LoadBalancer[]; operations: { id: string }[] }> {
  return request<{ loadBalancers: LoadBalancer[]; operations: { id: string }[] }>(
    "/api/load-balancers",
    {
      method: "POST",
      body: JSON.stringify(input)
    }
  );
}

export async function deleteLoadBalancer(
  id: string
): Promise<{ ok: boolean; operation: { id: string } }> {
  return request<{ ok: boolean; operation: { id: string } }>(
    `/api/load-balancers/${encodeURIComponent(id)}`,
    {
      method: "DELETE"
    }
  );
}

export async function updateLoadBalancer(
  id: string,
  input: {
    projectId?: string;
    nodeId?: string;
    type?: "nginx" | "haproxy" | "traefik";
    status?: string;
    listenPort?: number;
    config?: Record<string, unknown>;
  }
): Promise<{ loadBalancer: LoadBalancer }> {
  return request<{ loadBalancer: LoadBalancer }>(`/api/load-balancers/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(input)
  });
}
