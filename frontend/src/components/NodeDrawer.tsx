import { useEffect, useMemo, useState } from "react";

import EventCard from "./EventCard";
import MetricBar from "./MetricBar";
import type { EventRecord, ServerId, ServerState, WorldState } from "../types";
import { formatPercent, formatPower, formatTemp } from "../utils/format";
import {
  createOperation,
  refreshOperations,
  useOperationStore
} from "../state/operationStore";
import { createDraftPolicyForNode } from "../state/policyStore";

type NodeDrawerTab = "overview" | "metrics" | "events" | "operations" | "ai";

type NodeDrawerProps = {
  variant?: "drawer" | "page";
  open: boolean;
  nodeId: string | null;
  state: WorldState;
  events: EventRecord[];
  pinned?: boolean;
  onTogglePin?: () => void;
  onPopOut?: (nodeId: string) => void;
  onClose: () => void;
};

function getEventTarget(event: EventRecord): string | null {
  const payload = event.payload;
  if (!payload || typeof payload !== "object") return null;
  const maybeTarget = (payload as { target?: unknown }).target;
  if (typeof maybeTarget === "string" && maybeTarget.length > 0) return maybeTarget;
  return null;
}

function statusLabel(status: string | undefined) {
  if (status === "booting") return "Booting";
  if (status === "restarting") return "Restarting";
  if (status === "thermal_shutdown") return "Offline (thermal)";
  if (status === "off") return "Offline";
  return "Running";
}

function statusTone(status: string | undefined) {
  if (status === "booting" || status === "restarting") return "booting";
  if (status === "thermal_shutdown" || status === "off") return "off";
  return "running";
}

function cpuTone(load: number) {
  if (load > 85) return "tone-danger";
  if (load > 70) return "tone-warn";
  return "tone-ok";
}

function tempTone(temp: number) {
  if (temp > 85) return "tone-danger";
  if (temp > 70) return "tone-warn";
  return "tone-ok";
}

function errorTone(errorRate: number) {
  if (errorRate > 5) return "tone-danger";
  if (errorRate > 1) return "tone-warn";
  return "tone-ok";
}

function healthTone(health: number) {
  if (health < 60) return "tone-danger";
  if (health < 80) return "tone-warn";
  return "tone-ok";
}

export default function NodeDrawer({
  variant = "drawer",
  open,
  nodeId,
  state,
  events,
  pinned = false,
  onTogglePin,
  onPopOut,
  onClose
}: NodeDrawerProps) {
  const [tab, setTab] = useState<NodeDrawerTab>("overview");

  useEffect(() => {
    if (!open) return;
    setTab("overview");
  }, [open, nodeId]);

  useEffect(() => {
    if (!open) return;
    refreshOperations();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (variant !== "drawer") return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const onKeyDown = (event: KeyboardEvent) => {
      if (pinned) return;
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose, open]);

  const server = useMemo(() => {
    if (!nodeId) return null;
    const servers = state.servers as Record<ServerId, ServerState>;
    return (servers[nodeId] as ServerState | undefined) ?? null;
  }, [nodeId, state.servers]);

  const { operations } = useOperationStore();
  const nodeOperations = useMemo(() => {
    if (!nodeId) return [];
    return operations
      .filter((operation) => operation.targets.includes(nodeId))
      .slice(0, 8);
  }, [nodeId, operations]);

  const nodeEvents = useMemo(() => {
    if (!nodeId) return [];
    return events
      .filter((event) => getEventTarget(event) === nodeId)
      .slice()
      .reverse();
  }, [events, nodeId]);

  if (!open) return null;

  const panel = (
    <aside
      className={`node-drawer-panel ${variant === "page" ? "node-page-panel" : ""}`.trim()}
      role={variant === "page" ? "region" : "dialog"}
      aria-modal={variant === "page" ? undefined : "true"}
      aria-label={nodeId ? `Node ${nodeId}` : "Node"}
    >
      <div className="node-drawer-header">
        <div className="node-drawer-titleblock">
          <div className="node-drawer-eyebrow">Node</div>
          <div className="node-drawer-title">
            {nodeId ?? "-"}
            {server ? (
              <span className="node-inline-status">
                <span className={`status-dot status-${statusTone(server.status)}`} />
                <span>{statusLabel(server.status)}</span>
              </span>
            ) : null}
          </div>
        </div>

        <div className="node-drawer-actions">
          {variant === "drawer" ? (
            <button
              type="button"
              className={`node-drawer-icon ${pinned ? "active" : ""}`.trim()}
              aria-pressed={pinned}
              aria-label={pinned ? "Unpin" : "Pin"}
              onClick={() => onTogglePin?.()}
              disabled={!onTogglePin || !nodeId}
              title={pinned ? "Unpin" : "Pin"}
            >
              Pin
            </button>
          ) : null}

          {variant === "drawer" ? (
            <button
              type="button"
              className="node-drawer-icon"
              onClick={() => {
                if (!nodeId) return;
                onPopOut?.(nodeId);
              }}
              disabled={!nodeId || !onPopOut}
              title="Pop out"
            >
              Pop
            </button>
          ) : null}

          <button
            type="button"
            className="node-drawer-close"
            aria-label={variant === "page" ? "Back" : "Close"}
            onClick={onClose}
          >
            {variant === "page" ? "Back" : "X"}
          </button>
        </div>
      </div>

      <div className="node-drawer-tabs" role="tablist" aria-label="Node drawer tabs">
        {(
          [
            ["overview", "Overview"],
            ["metrics", "Metrics"],
            ["events", "Events"],
            ["operations", "Operations"],
            ["ai", "AI Analysis"]
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={`node-tab ${tab === key ? "active" : ""}`.trim()}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="node-drawer-body">
        {!server ? (
          <div className="card">
            <div className="card-title">Node not found</div>
            <p className="control-hint">
              This node id is not present in the current fleet provider.
            </p>
          </div>
        ) : tab === "overview" ? (
          <div className="node-stack">
            <div className="card">
              <div className="card-title">Identity</div>
              <div className="payload-grid">
                <div>
                  <div className="payload-label">Node id</div>
                  <div className="fleet-mono">{nodeId}</div>
                </div>
                <div>
                  <div className="payload-label">Provider</div>
                  <div>simulation</div>
                </div>
                <div>
                  <div className="payload-label">Status</div>
                  <div className="node-inline-status compact">
                    <span className={`status-dot status-${statusTone(server.status)}`} />
                    <span>{statusLabel(server.status)}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-title">Current metrics</div>
              <div className="node-metrics">
                <div className="node-metric">
                  <div className="node-metric-label">CPU</div>
                  <div className="node-metric-value">{formatPercent(server.load)}</div>
                  <MetricBar
                    value={server.load}
                    max={100}
                    tone={cpuTone(server.load)}
                    label="CPU utilization"
                  />
                </div>
                <div className="node-metric">
                  <div className="node-metric-label">Temp</div>
                  <div className="node-metric-value">{formatTemp(server.temp)}</div>
                  <MetricBar
                    value={server.temp}
                    max={110}
                    tone={tempTone(server.temp)}
                    label="Temperature"
                  />
                </div>
                <div className="node-metric">
                  <div className="node-metric-label">Error</div>
                  <div className="node-metric-value">{formatPercent(server.error_rate)}</div>
                  <MetricBar
                    value={server.error_rate}
                    max={20}
                    tone={errorTone(server.error_rate)}
                    label="Error rate"
                  />
                </div>
                <div className="node-metric">
                  <div className="node-metric-label">Health</div>
                  <div className="node-metric-value">{formatPercent(server.health)}</div>
                  <MetricBar
                    value={server.health}
                    max={100}
                    tone={healthTone(server.health)}
                    label="Health"
                  />
                </div>
                <div className="node-metric span-2">
                  <div className="node-metric-label">Power</div>
                  <div className="node-metric-value">{formatPower(server.power)}</div>
                  <MetricBar value={server.power} max={300} tone="tone-ink" label="Power draw" />
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-title">Quick actions</div>
              <div className="control-row">
                <button
                  type="button"
                  className="button outline"
                  onClick={() =>
                    nodeId && createOperation({ action: "maintenance_toggle", targets: [nodeId] })
                  }
                >
                  Maintenance
                </button>
                <button
                  type="button"
                  className="button outline"
                  onClick={() =>
                    nodeId && createOperation({ action: "health_check", targets: [nodeId] })
                  }
                >
                  Health check
                </button>
                <button
                  type="button"
                  className="button outline"
                  onClick={() =>
                    nodeId && createOperation({ action: "diagnostics", targets: [nodeId] })
                  }
                >
                  Diagnostics
                </button>
              </div>
              <div className="control-hint">
                Actions will create operations and appear in Operations.
              </div>
            </div>
          </div>
        ) : tab === "metrics" ? (
          <div className="card">
            <div className="card-title">Metrics</div>
            <p className="control-hint">
              Time series charts (CPU/Mem/Disk/Net) will appear here.
            </p>
          </div>
        ) : tab === "events" ? (
          <div className="node-stack">
            <div className="card">
              <div className="card-title">Node events</div>
              {nodeEvents.length === 0 ? (
                <div className="empty">No events for this node.</div>
              ) : (
                <div className="node-events">
                  {nodeEvents.slice(0, 50).map((event) => (
                    <EventCard key={event.id} event={event} variant="compact" />
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : tab === "operations" ? (
          <div className="node-stack">
            <div className="card">
              <div className="card-title">Operations</div>
              <div className="control-row">
                <button
                  type="button"
                  className="button outline"
                  onClick={() =>
                    nodeId && createOperation({ action: "restart_service", targets: [nodeId] })
                  }
                >
                  Restart service
                </button>
                <button
                  type="button"
                  className="button outline"
                  onClick={() =>
                    nodeId && createOperation({ action: "restart_host", targets: [nodeId] })
                  }
                >
                  Restart host
                </button>
                <button
                  type="button"
                  className="button outline"
                  onClick={() =>
                    nodeId && createOperation({ action: "run_script", targets: [nodeId] })
                  }
                >
                  Run script
                </button>
              </div>
              <div className="control-hint">
                Operations are queued in the log for audit.
              </div>
            </div>

            <div className="card">
              <div className="card-title">Recent operations</div>
              {nodeOperations.length === 0 ? (
                <div className="empty">No operations for this node yet.</div>
              ) : (
                <div className="node-command-list">
                  {nodeOperations.map((operation) => (
                    <div key={operation.id} className="node-command-row">
                      <div>
                        <div className="node-command-title">{operation.actionType}</div>
                        <div className="node-command-meta">{operation.status}</div>
                      </div>
                      <span className={`severity-badge severity-${operation.status}`}>
                        {operation.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="card">
            <div className="card-title">AI analysis</div>
            <p className="control-hint">
              AI analysis is user-triggered. Output will be stored to the event log.
            </p>
            <div className="control-row">
              <button type="button" className="button outline" disabled>
                Run analysis
              </button>
                <button
                  type="button"
                  className="button outline"
                  onClick={async () => {
                    if (!nodeId) return;
                    const policy = await createDraftPolicyForNode(nodeId);
                    const params = new URLSearchParams();
                    if (pinned) params.set("node", nodeId);
                    params.set("policy", policy.id);
                    window.location.hash = `/policies?${params.toString()}`;
                  }}
                >
                Create policy draft
              </button>
            </div>
          </div>
        )}
      </div>
    </aside>
  );

  if (variant === "page") {
    return (
      <div className="node-page">
        {panel}
      </div>
    );
  }

  return (
    <div className="node-drawer" role="presentation">
      <button
        type="button"
        className="node-drawer-backdrop"
        aria-label={pinned ? "Node drawer pinned" : "Close node drawer"}
        onClick={() => {
          if (pinned) return;
          onClose();
        }}
      />
      {panel}
    </div>
  );
}
