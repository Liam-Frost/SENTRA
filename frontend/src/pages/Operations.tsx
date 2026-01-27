import { useEffect, useMemo, useState } from "react";

import type { OperationStatus } from "../api/operations";
import {
  createOperation,
  refreshOperation,
  refreshOperations,
  useOperationStore
} from "../state/operationStore";

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString();
}

function parseParams() {
  let raw = window.location.hash;
  if (raw.startsWith("#/")) raw = raw.slice(2);
  else if (raw.startsWith("#")) raw = raw.slice(1);
  if (raw.startsWith("/")) raw = raw.slice(1);
  const [, query] = raw.split("?");
  return new URLSearchParams(query ?? "");
}

export default function OperationsPage() {
  const { operations, runs } = useOperationStore();
  const [statusFilter, setStatusFilter] = useState<OperationStatus | "all">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const handler = () => {
      const params = parseParams();
      setSelectedId(params.get("command"));
    };
    handler();
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  useEffect(() => {
    refreshOperations();
    const interval = window.setInterval(refreshOperations, 4000);
    return () => window.clearInterval(interval);
  }, []);

  const filtered = useMemo(() => {
    if (statusFilter === "all") return operations;
    return operations.filter((operation) => operation.status === statusFilter);
  }, [operations, statusFilter]);

  const selected = useMemo(() => {
    return operations.find((operation) => operation.id === selectedId) ?? filtered[0] ?? null;
  }, [filtered, operations, selectedId]);

  const operationRuns = useMemo(() => {
    if (!selected) return [];
    return runs.filter((run) => run.operationId === selected.id);
  }, [runs, selected]);

  useEffect(() => {
    if (!selected) return;
    refreshOperation(selected.id);
  }, [selected?.id]);

  const setSelected = (operationId: string) => {
    window.location.hash = `/operations?command=${encodeURIComponent(operationId)}`;
  };

  const retryFailed = () => {
    if (!selected) return;
    const failedNodes = operationRuns
      .filter((run) => run.status === "failed")
      .map((run) => run.nodeId);
    if (failedNodes.length === 0) return;
    createOperation({
      action: selected.actionType,
      targets: failedNodes.filter(Boolean) as string[],
      parameters: selected.parameters ?? undefined,
      initiator: "retry"
    });
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Command center</div>
          <h2 className="page-title">Operations</h2>
          <p className="page-description">
            Review operations, track execution progress, and audit results.
          </p>
        </div>
      </div>

      <div className="operations-layout">
        <section className="card operations-list">
          <div className="card-title">Operation list</div>
          <div className="operations-filters">
            <label htmlFor="commandStatus">Status</label>
            <select
              id="commandStatus"
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value as OperationStatus | "all")
              }
            >
              <option value="all">All</option>
              <option value="queued">Queued</option>
              <option value="running">Running</option>
              <option value="succeeded">Succeeded</option>
              <option value="failed">Failed</option>
              <option value="partial">Partial</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          <div className="command-list">
            {filtered.length === 0 ? (
              <div className="empty">No operations yet.</div>
            ) : (
              filtered.map((operation) => (
                <button
                  key={operation.id}
                  type="button"
                  className={`command-row ${selected?.id === operation.id ? "active" : ""}`.trim()}
                  onClick={() => setSelected(operation.id)}
                >
                  <div className="command-row-main">
                    <div className="command-row-title">{operation.actionType}</div>
                    <div className="command-row-meta">
                      {operation.targets.length} nodes · {formatTime(operation.createdAt)}
                    </div>
                  </div>
                  <span className={`severity-badge severity-${operation.status}`}>
                    {operation.status}
                  </span>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="card operations-detail">
          {!selected ? (
            <div className="empty">Select an operation to view details.</div>
          ) : (
            <div className="operations-detail-body">
              <div className="card-title">Operation detail</div>
              <div className="payload-grid">
                <div>
                  <div className="payload-label">Action</div>
                  <div>{selected.actionType}</div>
                </div>
                <div>
                  <div className="payload-label">Status</div>
                  <div className={`severity-badge severity-${selected.status}`}>{selected.status}</div>
                </div>
                <div>
                  <div className="payload-label">Targets</div>
                  <div>{selected.targets.length}</div>
                </div>
                <div>
                  <div className="payload-label">Initiator</div>
                  <div>{selected.initiator}</div>
                </div>
                <div>
                  <div className="payload-label">Approval</div>
                  <div>{selected.approvalState}</div>
                </div>
                <div>
                  <div className="payload-label">Created</div>
                  <div>{formatTime(selected.createdAt)}</div>
                </div>
              </div>

              <div className="operations-actions">
                <button type="button" className="button outline" onClick={retryFailed}>
                  Retry failed
                </button>
                <button type="button" className="button outline" disabled>
                  Export audit
                </button>
              </div>

              <div className="command-runs">
                <div className="command-runs-head">
                  <span>Node</span>
                  <span>Status</span>
                  <span>Result</span>
                </div>
                {operationRuns.map((run) => (
                  <div key={run.id} className="command-runs-row">
                    <span className="fleet-mono">{run.nodeId ?? "fleet"}</span>
                    <span>{run.status}</span>
                    <span>{run.output ?? "-"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
