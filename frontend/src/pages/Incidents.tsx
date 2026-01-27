import { useEffect, useMemo, useState } from "react";

import type { EventRecord, IncidentPayload, WorldState } from "../types";
import { createOperation } from "../state/operationStore";
import { createDraftPolicyFromIncident } from "../state/policyStore";

type IncidentSeverity = "critical" | "high" | "medium" | "low";
type IncidentStatus = "start" | "resolved";
type IncidentMetric = "temp" | "load" | "error_rate" | "health";

type IncidentItem = {
  id: number;
  tick: number;
  ts: string;
  message: string;
  target: string;
  metric: IncidentMetric;
  value: number;
  threshold: number;
  status: IncidentStatus;
  severity: IncidentSeverity;
  severityScore: number;
};

type IncidentsPageProps = {
  state: WorldState;
  events: EventRecord[];
};

const metricLabels: Record<IncidentMetric, string> = {
  temp: "Temperature",
  load: "CPU load",
  error_rate: "Error rate",
  health: "Health"
};

function parseHashPathAndParams() {
  let raw = window.location.hash;
  if (raw.startsWith("#/")) raw = raw.slice(2);
  else if (raw.startsWith("#")) raw = raw.slice(1);
  if (raw.startsWith("/")) raw = raw.slice(1);
  const [pathPart, queryPart] = raw.split("?");
  return {
    path: pathPart && pathPart.length > 0 ? pathPart : "dashboard",
    params: new URLSearchParams(queryPart ?? "")
  };
}

function parseIncidentPayload(event: EventRecord): IncidentPayload | null {
  if (event.type !== "incident") return null;
  const payload = event.payload as IncidentPayload | null;
  if (!payload || typeof payload !== "object") return null;
  if (!payload.metric || !payload.target) return null;
  return payload;
}

function ratioToSeverity(ratio: number): { severity: IncidentSeverity; score: number } {
  if (ratio >= 0.6) return { severity: "critical", score: 4 };
  if (ratio >= 0.35) return { severity: "high", score: 3 };
  if (ratio >= 0.15) return { severity: "medium", score: 2 };
  return { severity: "low", score: 1 };
}

function severityFromValue(metric: IncidentMetric, value: number, threshold: number) {
  if (metric === "health") {
    const ratio = threshold > 0 ? (threshold - value) / threshold : 0;
    return ratioToSeverity(ratio);
  }
  const ratio = threshold > 0 ? (value - threshold) / threshold : 0;
  return ratioToSeverity(ratio);
}

function normalizeStatus(payload: IncidentPayload): IncidentStatus {
  return payload.status === "resolved" ? "resolved" : "start";
}

function formatIsoTime(ts: string) {
  const parsed = new Date(ts);
  if (Number.isNaN(parsed.getTime())) return "-";
  return parsed.toLocaleTimeString();
}

export default function IncidentsPage({ state, events }: IncidentsPageProps) {
  const [statusFilter, setStatusFilter] = useState<IncidentStatus | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<IncidentSeverity | "all">("all");
  const [metricFilter, setMetricFilter] = useState<IncidentMetric | "all">("all");
  const [query, setQuery] = useState("");
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null);

  useEffect(() => {
    const handler = () => {
      const { params } = parseHashPathAndParams();
      const raw = params.get("event");
      if (!raw) {
        setSelectedEventId(null);
        return;
      }
      const parsed = Number(raw);
      setSelectedEventId(Number.isFinite(parsed) ? parsed : null);
    };

    handler();
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  const items = useMemo(() => {
    const next: IncidentItem[] = [];
    for (const event of events) {
      if (event.type !== "incident") continue;
      const payload = parseIncidentPayload(event);
      if (!payload) continue;
      const metric = payload.metric as IncidentMetric;
      const target = payload.target;
      const value = Number(payload.value ?? 0);
      const threshold = Number(payload.threshold ?? 1);
      const status = normalizeStatus(payload);
      const { severity, score } = severityFromValue(metric, value, threshold);
      next.push({
        id: event.id,
        tick: event.tick,
        ts: event.ts,
        message: event.message,
        target,
        metric,
        value,
        threshold,
        status,
        severity,
        severityScore: score
      });
    }

    next.sort((a, b) => b.id - a.id);
    return next;
  }, [events]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((item) => {
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (severityFilter !== "all" && item.severity !== severityFilter) return false;
      if (metricFilter !== "all" && item.metric !== metricFilter) return false;
      if (!needle) return true;

      const hay = `${item.target} ${item.metric} ${item.status} ${item.message}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [items, metricFilter, query, severityFilter, statusFilter]);

  const selected = useMemo(() => {
    if (filtered.length === 0) return null;
    if (selectedEventId !== null) {
      const found = filtered.find((item) => item.id === selectedEventId);
      if (found) return found;
    }
    return filtered[0];
  }, [filtered, selectedEventId]);

  const selectEvent = (eventId: number) => {
    const { params } = parseHashPathAndParams();
    params.set("event", String(eventId));
    const queryString = params.toString();
    setSelectedEventId(eventId);
    window.location.hash = queryString ? `/incidents?${queryString}` : "/incidents";
  };

  const openNode = (nodeId: string) => {
    const { params } = parseHashPathAndParams();
    params.set("node", nodeId);
    const queryString = params.toString();
    window.location.hash = queryString ? `/incidents?${queryString}` : "/incidents";
  };

  const affected = useMemo(() => {
    if (!selected) return [];
    const unique = new Set<string>();
    if (selected.target) unique.add(selected.target);
    return Array.from(unique);
  }, [selected]);

  const createOperationForTarget = () => {
    if (!selected) return;
    if (!selected.target) return;
    createOperation({
      action: "diagnostics",
      targets: [selected.target],
      parameters: {
        source: "incident",
        incident_event_id: selected.id,
        metric: selected.metric,
        status: selected.status
      },
      initiator: "incident"
    }).then((op) => {
      if (!op) return;
      window.location.hash = `/operations?command=${encodeURIComponent(op.id)}`;
    });
  };

  const createPolicyDraft = async () => {
    if (!selected) return;
    const policy = await createDraftPolicyFromIncident({
      target: selected.target,
      metric: selected.metric,
      threshold: selected.threshold,
      incidentEventId: selected.id,
      message: selected.message
    });

    const { params } = parseHashPathAndParams();
    const node = params.get("node");
    const nextParams = new URLSearchParams();
    if (node) nextParams.set("node", node);
    nextParams.set("policy", policy.id);
    window.location.hash = `/policies?${nextParams.toString()}`;
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Triage</div>
          <h2 className="page-title">Incidents</h2>
          <p className="page-description">Chronological incident events (start + resolved).</p>
        </div>
      </div>

      <div className="incident-layout">
        <section className="incident-panel card">
          <div className="incident-filters">
            <div className="fleet-search">
              <label htmlFor="incidentSearch">Search</label>
              <input
                id="incidentSearch"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="node id, metric, message"
              />
            </div>

            <div className="fleet-filter">
              <label htmlFor="incidentStatus">Status</label>
              <select
                id="incidentStatus"
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value as IncidentStatus | "all")
                }
              >
                <option value="all">All</option>
                <option value="start">Start</option>
                <option value="resolved">Resolved</option>
              </select>
            </div>

            <div className="fleet-filter">
              <label htmlFor="incidentSeverity">Severity</label>
              <select
                id="incidentSeverity"
                value={severityFilter}
                onChange={(event) =>
                  setSeverityFilter(event.target.value as IncidentSeverity | "all")
                }
              >
                <option value="all">All</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>

            <div className="fleet-filter">
              <label htmlFor="incidentMetric">Metric</label>
              <select
                id="incidentMetric"
                value={metricFilter}
                onChange={(event) =>
                  setMetricFilter(event.target.value as IncidentMetric | "all")
                }
              >
                <option value="all">All</option>
                <option value="temp">Temperature</option>
                <option value="load">CPU load</option>
                <option value="error_rate">Error rate</option>
                <option value="health">Health</option>
              </select>
            </div>
          </div>

          <div className="incident-list">
            {filtered.length === 0 ? (
              <div className="empty">No incident events match the current filters.</div>
            ) : (
              filtered.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`incident-item ${selected?.id === item.id ? "active" : ""}`.trim()}
                  onClick={() => selectEvent(item.id)}
                >
                  <div className="incident-title">
                    {metricLabels[item.metric]} · {item.target} · {item.status}
                  </div>
                  <div className="incident-meta">
                    <span className={`severity-badge severity-${item.severity}`}>{item.severity}</span>
                    <span>Tick {item.tick}</span>
                    <span>{formatIsoTime(item.ts)}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="incident-detail card">
          {!selected ? (
            <div className="empty">Select an incident event to view details.</div>
          ) : (
            <div className="incident-detail-body" key={selected.id}>
              <div>
                <div className="card-title">Summary</div>
                <div className="payload-grid">
                  <div>
                    <div className="payload-label">Node</div>
                    <div className="fleet-mono">{selected.target}</div>
                  </div>
                  <div>
                    <div className="payload-label">Metric</div>
                    <div>{metricLabels[selected.metric]}</div>
                  </div>
                  <div>
                    <div className="payload-label">Status</div>
                    <div>{selected.status}</div>
                  </div>
                  <div>
                    <div className="payload-label">Severity</div>
                    <div className={`severity-badge severity-${selected.severity}`}>{selected.severity}</div>
                  </div>
                  <div>
                    <div className="payload-label">Tick</div>
                    <div>T{selected.tick}</div>
                  </div>
                  <div>
                    <div className="payload-label">Value</div>
                    <div>{Number.isFinite(selected.value) ? selected.value.toFixed(1) : "-"}</div>
                  </div>
                  <div>
                    <div className="payload-label">Threshold</div>
                    <div>{Number.isFinite(selected.threshold) ? selected.threshold.toFixed(1) : "-"}</div>
                  </div>
                </div>
                <div className="control-hint">{selected.message}</div>
              </div>

              <div>
                <div className="card-title">Affected nodes</div>
                <div className="incident-nodes">
                  <div className="incident-node-head">
                    <span>Node</span>
                    <span>Status</span>
                    <span>Value</span>
                  </div>
                  {affected.map((nodeId) => {
                    const server = state.servers[nodeId];
                    const currentValue = server ? (server as any)[selected.metric] ?? 0 : 0;
                    return (
                      <button
                        key={nodeId}
                        type="button"
                        className="incident-node-row"
                        onClick={() => openNode(nodeId)}
                      >
                        <span className="fleet-mono">{nodeId}</span>
                        <span>{server?.status ?? "unknown"}</span>
                        <span>
                          {Number.isFinite(Number(currentValue))
                            ? Number(currentValue).toFixed(1)
                            : "-"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="incident-actions">
                <button type="button" className="button outline" onClick={createPolicyDraft}>
                  Generate policy draft
                </button>
                <button type="button" className="button primary" onClick={createOperationForTarget}>
                  Create operation
                </button>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
