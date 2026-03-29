import { useEffect, useMemo, useState } from "react";

import { listNodes, listProjects, type Node, type Project } from "../api/infrastructure";
import {
  applyLbPolicy,
  createLbPolicy,
  deleteLbPolicy,
  listLbPolicies,
  updateLbPolicy,
  type LbPolicy,
  type LbPolicyAllocation
} from "../api/lbPolicies";
import { formatDateTime } from "../utils/format";

type PolicyDraft = {
  projectId: string;
  name: string;
  description: string;
  status: "draft" | "active";
  drMode: "manual" | "active-standby" | "weighted-failover";
  healthCheckPath: string;
  healthCheckIntervalSec: number;
  failureThreshold: number;
  recoveryThreshold: number;
  autoFailback: boolean;
  allocations: LbPolicyAllocation[];
};

function createEmptyDraft(projectId = "", nodes: Node[] = []): PolicyDraft {
  return {
    projectId,
    name: "",
    description: "",
    status: "draft",
    drMode: "manual",
    healthCheckPath: "/healthz",
    healthCheckIntervalSec: 10,
    failureThreshold: 3,
    recoveryThreshold: 2,
    autoFailback: false,
    allocations: nodes.map((node, index) => ({
      nodeId: node.id,
      enabled: false,
      weight: 0,
      priority: index + 1
    }))
  };
}

function normalizeAllocations(nodes: Node[], allocations: LbPolicyAllocation[]) {
  return nodes.map((node, index) => {
    const existing = allocations.find((item) => item.nodeId === node.id);
    return {
      nodeId: node.id,
      enabled: existing?.enabled ?? false,
      weight: existing?.weight ?? 0,
      priority: existing?.priority ?? index + 1
    };
  });
}

export default function PoliciesPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [policies, setPolicies] = useState<LbPolicy[]>([]);
  const [projectFilter, setProjectFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastAppliedExecutionId, setLastAppliedExecutionId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null);
  const [draft, setDraft] = useState<PolicyDraft>(createEmptyDraft());

  const loadAll = async () => {
    setLoading(true);
    try {
      const [projectData, nodeData, policyData] = await Promise.all([
        listProjects(),
        listNodes(),
        listLbPolicies()
      ]);
      const nextProjects = Array.isArray(projectData.projects) ? projectData.projects : [];
      const nextNodes = Array.isArray(nodeData.nodes) ? nodeData.nodes : [];
      const nextPolicies = Array.isArray(policyData.policies) ? policyData.policies : [];
      setProjects(nextProjects);
      setNodes(nextNodes);
      setPolicies(nextPolicies);
      setProjectFilter((current) => current || nextProjects[0]?.id || "");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load LB policies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const filteredPolicies = useMemo(() => {
    const byProject = projectFilter ? policies.filter((policy) => policy.projectId === projectFilter) : policies;
    const needle = query.trim().toLowerCase();
    if (!needle) return byProject;
    return byProject.filter((policy) => {
      const hay = `${policy.name} ${policy.projectId} ${policy.description ?? ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [policies, projectFilter, query]);

  const selectedPolicy = useMemo(
    () => policies.find((policy) => policy.id === selectedPolicyId) ?? null,
    [policies, selectedPolicyId]
  );

  const openCreate = () => {
    setDraft(createEmptyDraft(projectFilter || projects[0]?.id || "", nodes));
    setCreateOpen(true);
    setError(null);
  };

  const closeCreate = () => {
    setCreateOpen(false);
    setDraft(createEmptyDraft(projectFilter || projects[0]?.id || "", nodes));
  };

  const openEdit = (policy: LbPolicy) => {
    setSelectedPolicyId(policy.id);
    setDraft({
      projectId: policy.projectId,
      name: policy.name,
      description: policy.description || "",
      status: policy.status,
      drMode: policy.drMode,
      healthCheckPath: policy.healthCheckPath || "/healthz",
      healthCheckIntervalSec: policy.healthCheckIntervalSec,
      failureThreshold: policy.failureThreshold,
      recoveryThreshold: policy.recoveryThreshold,
      autoFailback: policy.autoFailback,
      allocations: normalizeAllocations(nodes, policy.allocations)
    });
    setEditOpen(true);
    setError(null);
  };

  const closeEdit = () => {
    setEditOpen(false);
    setSelectedPolicyId(null);
  };

  const updateAllocation = (nodeId: string, patch: Partial<LbPolicyAllocation>) => {
    setDraft((current) => ({
      ...current,
      allocations: current.allocations.map((allocation) =>
        allocation.nodeId === nodeId ? { ...allocation, ...patch } : allocation
      )
    }));
  };

  const allocationTotal = useMemo(
    () => draft.allocations.filter((item) => item.enabled).reduce((sum, item) => sum + Number(item.weight || 0), 0),
    [draft.allocations]
  );

  const persistDraft = async (mode: "create" | "edit") => {
    if (!draft.projectId) {
      setError("Select a project");
      return;
    }
    if (!draft.name.trim()) {
      setError("Policy name is required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        projectId: draft.projectId,
        name: draft.name.trim(),
        description: draft.description.trim(),
        status: draft.status,
        drMode: draft.drMode,
        healthCheckPath: draft.healthCheckPath.trim() || "/healthz",
        healthCheckIntervalSec: Number(draft.healthCheckIntervalSec) || 10,
        failureThreshold: Number(draft.failureThreshold) || 3,
        recoveryThreshold: Number(draft.recoveryThreshold) || 2,
        autoFailback: draft.autoFailback,
        allocations: draft.allocations.map((allocation) => ({
          nodeId: allocation.nodeId,
          enabled: allocation.enabled,
          weight: Number(allocation.weight) || 0,
          priority: Number(allocation.priority) || 1
        }))
      };
      if (mode === "create") {
        await createLbPolicy(payload);
        closeCreate();
      } else if (selectedPolicyId) {
        await updateLbPolicy(selectedPolicyId, payload);
        closeEdit();
      }
      setLastAppliedExecutionId(null);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save policy");
    } finally {
      setSaving(false);
    }
  };

  const removeSelectedPolicy = async () => {
    if (!selectedPolicyId) return;
    setSaving(true);
    try {
      await deleteLbPolicy(selectedPolicyId);
      await loadAll();
      closeEdit();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete policy");
    } finally {
      setSaving(false);
    }
  };

  const applySelectedPolicy = async () => {
    if (!selectedPolicyId) return;
    setSaving(true);
    try {
      const result = await applyLbPolicy(selectedPolicyId, "policy");
      setLastAppliedExecutionId(result.execution.id);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply policy");
    } finally {
      setSaving(false);
    }
  };

  const renderEditor = (mode: "create" | "edit") => (
    <div className="policy-form">
      <div className="policy-form-row">
        <div className="policy-field">
          <label htmlFor={`${mode}-lbPolicyProject`}>Project</label>
          <select
            id={`${mode}-lbPolicyProject`}
            value={draft.projectId}
            onChange={(event) => setDraft((current) => ({ ...current, projectId: event.target.value }))}
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>
        <div className="policy-field">
          <label htmlFor={`${mode}-lbPolicyStatus`}>Status</label>
          <select
            id={`${mode}-lbPolicyStatus`}
            value={draft.status}
            onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value as PolicyDraft["status"] }))}
          >
            <option value="draft">draft</option>
            <option value="active">active</option>
          </select>
        </div>
        <div className="policy-field">
          <label htmlFor={`${mode}-lbPolicyMode`}>DR mode</label>
          <select
            id={`${mode}-lbPolicyMode`}
            value={draft.drMode}
            onChange={(event) => setDraft((current) => ({ ...current, drMode: event.target.value as PolicyDraft["drMode"] }))}
          >
            <option value="manual">manual</option>
            <option value="active-standby">active-standby</option>
            <option value="weighted-failover">weighted-failover</option>
          </select>
        </div>
      </div>

      <div className="policy-form-row">
        <div className="policy-field policy-field-wide">
          <label htmlFor={`${mode}-lbPolicyName`}>Name</label>
          <input
            id={`${mode}-lbPolicyName`}
            value={draft.name}
            onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
            placeholder="Primary traffic allocation"
          />
        </div>
      </div>

      <div className="policy-field">
        <label htmlFor={`${mode}-lbPolicyDescription`}>Description</label>
        <textarea
          id={`${mode}-lbPolicyDescription`}
          rows={3}
          value={draft.description}
          onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
          placeholder="Describe how this project should distribute traffic"
        />
      </div>

      <div className="policy-section">
        <div className="policy-section-title">Traffic Allocation</div>
        <div className="control-hint">Enabled node weights should add up to 100. Current total: {allocationTotal}</div>
        <div className="command-runs">
          <div className="command-runs-head">
            <span>Node</span>
            <span>Enabled</span>
            <span>Weight / Priority</span>
          </div>
          {draft.allocations.map((allocation) => {
            const node = nodes.find((item) => item.id === allocation.nodeId);
            return (
              <div key={`${mode}-${allocation.nodeId}`} className="command-runs-row">
                <span className="fleet-mono">{node?.hostname ?? allocation.nodeId}</span>
                <span>
                  <input
                    type="checkbox"
                    checked={allocation.enabled}
                    onChange={(event) => updateAllocation(allocation.nodeId, { enabled: event.target.checked })}
                  />
                </span>
                <span className="operations-actions">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={allocation.weight}
                    onChange={(event) => updateAllocation(allocation.nodeId, { weight: Number(event.target.value) || 0 })}
                    style={{ maxWidth: "120px" }}
                  />
                  <input
                    type="number"
                    min={1}
                    value={allocation.priority}
                    onChange={(event) => updateAllocation(allocation.nodeId, { priority: Number(event.target.value) || 1 })}
                    style={{ maxWidth: "120px" }}
                  />
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="policy-section">
        <div className="policy-section-title">Disaster Recovery</div>
        <div className="policy-form-row">
          <div className="policy-field">
            <label htmlFor={`${mode}-lbPolicyHealthPath`}>Health check path</label>
            <input
              id={`${mode}-lbPolicyHealthPath`}
              value={draft.healthCheckPath}
              onChange={(event) => setDraft((current) => ({ ...current, healthCheckPath: event.target.value }))}
            />
          </div>
          <div className="policy-field">
            <label htmlFor={`${mode}-lbPolicyInterval`}>Interval (sec)</label>
            <input
              id={`${mode}-lbPolicyInterval`}
              type="number"
              min={1}
              value={draft.healthCheckIntervalSec}
              onChange={(event) => setDraft((current) => ({ ...current, healthCheckIntervalSec: Number(event.target.value) || 10 }))}
            />
          </div>
          <div className="policy-field">
            <label htmlFor={`${mode}-lbPolicyFailureThreshold`}>Failure threshold</label>
            <input
              id={`${mode}-lbPolicyFailureThreshold`}
              type="number"
              min={1}
              value={draft.failureThreshold}
              onChange={(event) => setDraft((current) => ({ ...current, failureThreshold: Number(event.target.value) || 3 }))}
            />
          </div>
          <div className="policy-field">
            <label htmlFor={`${mode}-lbPolicyRecoveryThreshold`}>Recovery threshold</label>
            <input
              id={`${mode}-lbPolicyRecoveryThreshold`}
              type="number"
              min={1}
              value={draft.recoveryThreshold}
              onChange={(event) => setDraft((current) => ({ ...current, recoveryThreshold: Number(event.target.value) || 2 }))}
            />
          </div>
        </div>

        <label className="action-field-inline">
          <input
            type="checkbox"
            checked={draft.autoFailback}
            onChange={(event) => setDraft((current) => ({ ...current, autoFailback: event.target.checked }))}
          />
          <span>Auto failback after recovery</span>
        </label>
      </div>
    </div>
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Traffic Control</div>
          <h2 className="page-title">Policies</h2>
        </div>
        <div className="page-actions">
          <label className="fleet-filter">
            <span>Project</span>
            <select value={projectFilter} onChange={(event) => setProjectFilter(event.target.value)}>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>{project.name}</option>
              ))}
            </select>
          </label>
          <button type="button" className="button primary" onClick={openCreate}>Add policy</button>
        </div>
      </div>

      {error ? (
        <div className="alert"><strong>Error:</strong> {error}</div>
      ) : null}

      {lastAppliedExecutionId ? (
        <div className="alert"><strong>Apply queued:</strong> execution {lastAppliedExecutionId}</div>
      ) : null}

      <section className="card library-page-card">
        <div className="library-page-head">
          <div>
            <div className="card-title">Policy library</div>
            <div className="control-hint">Browse policies by project. Open one to edit traffic allocation or DR behavior.</div>
          </div>
        </div>

        <div className="fleet-search">
          <label htmlFor="policySearch">Search</label>
          <input
            id="policySearch"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="policy name, project, description"
          />
        </div>

        {loading ? <div className="empty">Loading policies...</div> : null}
        {!loading && filteredPolicies.length === 0 ? <div className="empty">No policies found for this project.</div> : null}

        {!loading && filteredPolicies.length > 0 ? (
          <div className="library-grid">
            {filteredPolicies.map((policy) => (
              <button key={policy.id} type="button" className="library-card" onClick={() => openEdit(policy)}>
                <div className="library-card-head">
                  <div className="library-card-title">{policy.name}</div>
                  <span className={`severity-badge severity-${policy.status}`}>{policy.status}</span>
                </div>
                <div className="library-card-meta">{policy.drMode}</div>
                <div className="library-card-description">{policy.description || "No description yet."}</div>
                <div className="library-card-time">Updated {formatDateTime(policy.updatedAt)}</div>
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {createOpen ? (
        <div className="overlay-shell" role="presentation" onClick={closeCreate}>
          <div className="overlay-panel" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="overlay-head">
              <div>
                <div className="card-title">Create policy</div>
              </div>
              <button type="button" className="button outline" onClick={closeCreate}>Close</button>
            </div>
            <div className="overlay-body">
              {renderEditor("create")}
              <div className="overlay-actions">
                <div className="spacer" />
                <button type="button" className="button primary" disabled={saving} onClick={() => persistDraft("create")}>
                  {saving ? "Creating..." : "Create policy"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {editOpen && selectedPolicy ? (
        <div className="overlay-shell" role="presentation" onClick={closeEdit}>
          <div className="overlay-panel" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="overlay-head">
              <div>
                <div className="card-title">Policy editor</div>
              </div>
              <button type="button" className="button outline" onClick={closeEdit}>Close</button>
            </div>
            <div className="overlay-body">
              <div className="payload-grid">
                <div>
                  <div className="payload-label">Policy ID</div>
                  <div className="fleet-mono">{selectedPolicy.id}</div>
                </div>
                <div>
                  <div className="payload-label">Created</div>
                  <div>{formatDateTime(selectedPolicy.createdAt)}</div>
                </div>
                <div>
                  <div className="payload-label">Updated</div>
                  <div>{formatDateTime(selectedPolicy.updatedAt)}</div>
                </div>
              </div>

              {renderEditor("edit")}

              <div className="overlay-actions">
                <button type="button" className="button outline" disabled={saving} onClick={removeSelectedPolicy}>Delete</button>
                <div className="spacer" />
                <button type="button" className="button outline" disabled={saving} onClick={applySelectedPolicy}>Apply</button>
                <button type="button" className="button primary" disabled={saving} onClick={() => persistDraft("edit")}>
                  {saving ? "Saving..." : "Save policy"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
