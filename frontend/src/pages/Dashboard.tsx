import { useEffect, useMemo, useState } from "react";

import AnimatedList from "../components/AnimatedList";
import EventCard from "../components/EventCard";
import MetricBar from "../components/MetricBar";
import NumberTicker from "../components/NumberTicker";
import type { EventRecord, WorldState } from "../types";
import { formatDateTime, formatPercent } from "../utils/format";
import { getDashboard, type DashboardResponse } from "../api/infrastructure";

type DashboardProps = {
  state: WorldState;
  events: EventRecord[];
  incidentCount: number;
  simulationEnabled?: boolean;
  lastUpdated?: Date | null;
  onOpenEvents: (eventId?: number) => void;
};

const EMPTY_DASHBOARD: DashboardResponse = {
  summary: {
    totalNodes: 0,
    onlineNodes: 0,
    offlineNodes: 0,
    incidentNodes: 0,
    avgCpu: 0,
    avgMemory: 0,
    avgDisk: 0,
    projects: 0,
    loadBalancers: 0,
    policies: 0,
    activePolicies: 0,
    templates: 0,
    executions: 0,
    runningExecutions: 0,
    queuedExecutions: 0
  },
  nodes: [],
  recentExecutions: []
};

export default function Dashboard({
  state: _state,
  events,
  incidentCount,
  simulationEnabled: _simulationEnabled = false,
  lastUpdated = null,
  onOpenEvents
}: DashboardProps) {
  const [dashboard, setDashboard] = useState<DashboardResponse>(EMPTY_DASHBOARD);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await getDashboard();
        if (cancelled) return;
        setDashboard(data);
      } catch {
        if (cancelled) return;
      }
    };

    load();
    const interval = window.setInterval(load, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const summary = dashboard.summary;
  const recentEvents = useMemo(() => [...events].reverse().slice(0, 4), [events]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Overview</div>
          <h2 className="page-title">Dashboard</h2>
        </div>
        <div className="page-status">
          <div className="status-chip">Projects {summary.projects}</div>
          <div className="status-chip">LB nodes {summary.loadBalancers}</div>
          <div className="status-chip">Incidents {incidentCount}</div>
        </div>
      </div>

      <section className="stats-grid dashboard-product-grid">
        <div className="card stat-card span-2x1">
          <div className="card-title">Fleet coverage</div>
          <div className="stat-value"><NumberTicker value={summary.totalNodes} /></div>
          <div className="stat-sub">Registered nodes</div>
          <div className="stat-row"><span>Online</span><span className="stat-inline">{summary.onlineNodes}</span></div>
          <div className="stat-row"><span>Offline</span><span className="stat-inline">{summary.offlineNodes}</span></div>
          <div className="stat-row"><span>Incident nodes</span><span className="stat-inline">{summary.incidentNodes}</span></div>
        </div>

        <div className="card stat-card span-2x1">
          <div className="card-title">Project surface</div>
          <div className="stat-value"><NumberTicker value={summary.projects} /></div>
          <div className="stat-sub">Projects under management</div>
          <div className="stat-row"><span>Load balancer nodes</span><span className="stat-inline">{summary.loadBalancers}</span></div>
          <div className="stat-row"><span>Policies</span><span className="stat-inline">{summary.policies}</span></div>
          <div className="stat-row"><span>Active policies</span><span className="stat-inline">{summary.activePolicies}</span></div>
        </div>

        <div className="card stat-card span-2x1">
          <div className="card-title">Automation surface</div>
          <div className="stat-value"><NumberTicker value={summary.templates} /></div>
          <div className="stat-sub">Operation templates</div>
          <div className="stat-row"><span>Total executions</span><span className="stat-inline">{summary.executions}</span></div>
          <div className="stat-row"><span>Running</span><span className="stat-inline">{summary.runningExecutions}</span></div>
          <div className="stat-row"><span>Queued</span><span className="stat-inline">{summary.queuedExecutions}</span></div>
        </div>

        <div className="card stat-card span-2x1">
          <div className="card-title">Capacity snapshot</div>
          <div className="metric">
            <div className="metric-row"><span>Average CPU</span><strong>{formatPercent(summary.avgCpu)}</strong></div>
            <MetricBar value={summary.avgCpu} max={100} tone="tone-ok" label="Average CPU" />
          </div>
          <div className="metric">
            <div className="metric-row"><span>Average memory</span><strong>{formatPercent(summary.avgMemory)}</strong></div>
            <MetricBar value={summary.avgMemory} max={100} tone="tone-warn" label="Average memory" />
          </div>
          <div className="metric">
            <div className="metric-row"><span>Average disk</span><strong>{formatPercent(summary.avgDisk)}</strong></div>
            <MetricBar value={summary.avgDisk} max={100} tone="tone-ink" label="Average disk" />
          </div>
        </div>

        <div className="card stat-card span-4x1">
          <div className="card-title">Recent executions</div>
          {dashboard.recentExecutions.length === 0 ? (
            <div className="empty">No operation executions yet.</div>
          ) : (
            <div className="command-list">
              {dashboard.recentExecutions.map((execution, index) => (
                <div key={`${execution.templateId ?? "execution"}-${execution.createdAt}-${index}`} className="command-row" style={{ cursor: "default" }}>
                  <div className="command-row-main">
                    <div className="command-row-title">{execution.templateName || "Untitled template"}</div>
                    <div className="command-row-meta">
                      {execution.targetCount} nodes · {formatDateTime(execution.createdAt)}
                    </div>
                  </div>
                  <span className={`severity-badge severity-${execution.status}`}>{execution.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card stat-card span-4x1">
          <div className="card-title">Recent events</div>
          {recentEvents.length === 0 ? (
            <div className="empty">No events yet.</div>
          ) : (
            <AnimatedList
              items={recentEvents}
              getKey={(event) => event.id}
              renderItem={(event) => (
                <button type="button" className="event-link" onClick={() => onOpenEvents(event.id)}>
                  <EventCard event={event} variant="compact" />
                </button>
              )}
              itemClassName="event-compact-wrapper"
            />
          )}
          <div className="stat-row">
            <span>Snapshot time</span>
            <span className="stat-inline">{lastUpdated ? formatDateTime(lastUpdated) : "-"}</span>
          </div>
        </div>
      </section>
    </div>
  );
}
