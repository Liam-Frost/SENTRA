import { useEffect, useMemo, useState } from "react";

import type { WorldState } from "../types";
import {
  ActionStep,
  ActionType,
  Condition,
  ConditionMetric,
  ConditionOp,
  Policy,
  PolicyMode,
  PolicyStatus,
  computeRiskLevel,
  createPolicy,
  deletePolicy,
  duplicatePolicy,
  savePolicy,
  usePolicyStore,
  validatePolicy,
  getAvailableActions,
  getActionCatalogItem
} from "../state/policyStore";
import { runPolicyApi } from "../api/policies";

type PoliciesPageProps = {
  state: WorldState;
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

function scopeSummary(policy: Policy) {
  if (policy.scope.type === "all") return "All nodes";
  if (policy.scope.type === "nodes") {
    const ids = policy.scope.nodeIds ?? [];
    if (ids.length === 0) return "No nodes selected";
    if (ids.length <= 3) return `Nodes: ${ids.join(", ")}`;
    return `Nodes: ${ids.length}`;
  }
  if (policy.scope.type === "tag") return "Tag selector";
  if (policy.scope.type === "group") return "Group selector";
  return "Scope";
}

function formatActionLabel(type: ActionType) {
  const found = getActionCatalogItem(type);
  return found?.label ?? type;
}

function isDurationUnsupported(policy: Policy) {
  return policy.conditions.items.some((condition) =>
    typeof condition.durationSec === "number" && condition.durationSec > 0
  );
}

function parseNodeIds(raw: string) {
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function stringifyNodeIds(ids: string[]) {
  return ids.join(", ");
}

function computeMatches(state: WorldState, policy: Policy) {
  const allNodes = Object.keys(state.servers);
  const candidates = (() => {
    if (policy.scope.type === "all") return allNodes;
    if (policy.scope.type === "nodes") {
      const ids = policy.scope.nodeIds ?? [];
      return ids.filter((id) => allNodes.includes(id));
    }
    return allNodes;
  })();

  const conditions = policy.conditions.items;
  if (conditions.length === 0) {
    return candidates;
  }

  const evaluate = (nodeId: string) => {
    const server = state.servers[nodeId] as any;
    if (!server) return false;

    const checks = conditions.map((condition) => {
      const value = Number(server[condition.metric] ?? 0);
      const target = Number(condition.value ?? 0);
      const op = condition.op;
      if (op === ">") return value > target;
      if (op === ">=") return value >= target;
      if (op === "<") return value < target;
      return value <= target;
    });

    if (policy.conditions.op === "OR") return checks.some(Boolean);
    return checks.every(Boolean);
  };

  return candidates.filter(evaluate);
}

function defaultCondition(): Condition {
  return { metric: "load", op: ">", value: 85, durationSec: 60 };
}

function defaultAction(): ActionStep {
  return {
    type: "enableCooling",
    capability: "simulation",
    availability: "available"
  };
}

export default function PoliciesPage({ state }: PoliciesPageProps) {
  const { policies } = usePolicyStore();
  const [query, setQuery] = useState("");
  const [modeFilter, setModeFilter] = useState<PolicyMode | "all">("all");
  const [statusFilter, setStatusFilter] = useState<PolicyStatus | "all">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Policy | null>(null);
  const [savedSnapshot, setSavedSnapshot] = useState<string>("");
  const [runBusy, setRunBusy] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  useEffect(() => {
    const handler = () => {
      const { params } = parseHashPathAndParams();
      const policyId = params.get("policy");
      setSelectedId(policyId);
    };
    handler();
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return policies.filter((policy) => {
      if (modeFilter !== "all" && policy.mode !== modeFilter) return false;
      if (statusFilter !== "all" && policy.status !== statusFilter) return false;
      if (!needle) return true;
      const hay = `${policy.name} ${policy.notes ?? ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [modeFilter, policies, query, statusFilter]);

  const selected = useMemo(() => {
    if (filtered.length === 0) return null;
    if (selectedId) {
      const found = filtered.find((policy) => policy.id === selectedId);
      if (found) return found;
    }
    return filtered[0];
  }, [filtered, selectedId]);

  useEffect(() => {
    if (!selected) {
      setDraft(null);
      setSavedSnapshot("");
      return;
    }
    const copy = JSON.parse(JSON.stringify(selected)) as Policy;
    setDraft(copy);
    setSavedSnapshot(JSON.stringify(selected));
  }, [selected?.id]);

  const unsaved = useMemo(() => {
    if (!draft) return false;
    return JSON.stringify(draft) !== savedSnapshot;
  }, [draft, savedSnapshot]);

  const derivedRisk = useMemo(() => {
    return draft ? computeRiskLevel(draft.actions) : 0;
  }, [draft]);

  const errors = useMemo(() => (draft ? validatePolicy({ ...draft, riskLevel: derivedRisk }) : []), [draft, derivedRisk]);

  const matchPreview = useMemo(() => {
    if (!draft) return { matched: [], unsupportedDuration: false };
    return {
      matched: computeMatches(state, draft),
      unsupportedDuration: isDurationUnsupported(draft)
    };
  }, [draft, state]);

  const selectPolicy = (id: string) => {
    const { params } = parseHashPathAndParams();
    params.set("policy", id);
    const queryString = params.toString();
    window.location.hash = queryString ? `/policies?${queryString}` : "/policies";
  };

  const createNewPolicy = async () => {
    const policy = await createPolicy({ name: "New policy", status: "draft" });
    selectPolicy(policy.id);
  };

  const doDuplicate = async () => {
    if (!selected) return;
    const copy = await duplicatePolicy(selected.id);
    if (!copy) return;
    selectPolicy(copy.id);
  };

  const doDelete = async () => {
    if (!selected) return;
    await deletePolicy(selected.id);
    const { params } = parseHashPathAndParams();
    params.delete("policy");
    const queryString = params.toString();
    window.location.hash = queryString ? `/policies?${queryString}` : "/policies";
  };

  const doSave = async () => {
    if (!draft) return;
    const next = await savePolicy({
      ...draft,
      riskLevel: derivedRisk
    });
    setSavedSnapshot(JSON.stringify(next));
    setDraft(JSON.parse(JSON.stringify(next)) as Policy);
  };

  const runPolicyNow = async () => {
    if (!draft) return;
    setRunBusy(true);
    try {
      await runPolicyApi(draft.id);
      setRunError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to run policy";
      setRunError(message);
    } finally {
      setRunBusy(false);
    }
  };

  const updateDraft = (patch: Partial<Policy>) => {
    if (!draft) return;
    setDraft({ ...draft, ...patch });
  };

  const updateScopeNodes = (raw: string) => {
    if (!draft) return;
    updateDraft({
      scope: { ...draft.scope, type: "nodes", nodeIds: parseNodeIds(raw) }
    });
  };

  const addCondition = () => {
    if (!draft) return;
    updateDraft({
      conditions: {
        ...draft.conditions,
        items: [...draft.conditions.items, defaultCondition()]
      }
    });
  };

  const updateCondition = (index: number, patch: Partial<Condition>) => {
    if (!draft) return;
    const next = draft.conditions.items.map((condition, idx) =>
      idx === index ? { ...condition, ...patch } : condition
    );
    updateDraft({ conditions: { ...draft.conditions, items: next } });
  };

  const removeCondition = (index: number) => {
    if (!draft) return;
    const next = draft.conditions.items.filter((_, idx) => idx !== index);
    updateDraft({ conditions: { ...draft.conditions, items: next } });
  };

  const addAction = () => {
    if (!draft) return;
    updateDraft({ actions: [...draft.actions, defaultAction()] });
  };

  const updateAction = (index: number, patch: Partial<ActionStep>) => {
    if (!draft) return;
    const next = draft.actions.map((action, idx) =>
      idx === index ? { ...action, ...patch } : action
    );
    updateDraft({ actions: next });
  };

  const moveAction = (index: number, direction: -1 | 1) => {
    if (!draft) return;
    const next = [...draft.actions];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    const temp = next[index];
    next[index] = next[target];
    next[target] = temp;
    updateDraft({ actions: next });
  };

  const removeAction = (index: number) => {
    if (!draft) return;
    const next = draft.actions.filter((_, idx) => idx !== index);
    updateDraft({ actions: next });
  };

  const toggleEnabled = async (id: string) => {
    const policy = policies.find((p) => p.id === id);
    if (!policy) return;
    const updated = await savePolicy({ ...policy, enabled: !policy.enabled });
    if (draft && draft.id === updated.id) {
      setDraft(JSON.parse(JSON.stringify(updated)) as Policy);
      setSavedSnapshot(JSON.stringify(updated));
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Orchestration</div>
          <h2 className="page-title">Policies</h2>
          <p className="page-description">
            Draft, validate, and manage autonomy policies. Stored in the backend (cached locally).
          </p>
        </div>
      </div>

      <div className="policies-layout">
        <section className="card policies-list">
          <div className="policies-list-head">
            <div className="card-title">Policy list</div>
            <button type="button" className="button primary" onClick={createNewPolicy}>
              New
            </button>
          </div>

          <div className="policies-filters">
            <div className="fleet-search">
              <label htmlFor="policySearch">Search</label>
              <input
                id="policySearch"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="name or notes"
              />
            </div>
            <div className="fleet-filter">
              <label htmlFor="policyMode">Mode</label>
              <select
                id="policyMode"
                value={modeFilter}
                onChange={(event) => setModeFilter(event.target.value as PolicyMode | "all")}
              >
                <option value="all">All</option>
                <option value="ADVISE_ONLY">ADVISE_ONLY</option>
                <option value="AUTO_EXECUTE">AUTO_EXECUTE</option>
              </select>
            </div>
            <div className="fleet-filter">
              <label htmlFor="policyStatus">Status</label>
              <select
                id="policyStatus"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as PolicyStatus | "all")}
              >
                <option value="all">All</option>
                <option value="draft">draft</option>
                <option value="active">active</option>
                <option value="archived">archived</option>
              </select>
            </div>
          </div>

          <div className="policies-rows">
            {filtered.length === 0 ? (
              <div className="empty">No policies yet.</div>
            ) : (
              filtered.map((policy) => (
                <button
                  key={policy.id}
                  type="button"
                  className={`policy-row ${selected?.id === policy.id ? "active" : ""}`.trim()}
                  onClick={() => selectPolicy(policy.id)}
                >
                  <div className="policy-row-main">
                    <div className="policy-row-title">
                      {policy.name}
                      <span className="policy-row-badge">v{policy.version}</span>
                    </div>
                    <div className="policy-row-meta">
                      <span className={`severity-badge severity-${policy.status}`}>{policy.status}</span>
                      <span className="severity-badge">{policy.mode}</span>
                      <span>p{policy.priority}</span>
                      <span>{scopeSummary(policy)}</span>
                    </div>
                  </div>

                  <input
                    type="checkbox"
                    className="policy-toggle"
                    checked={policy.enabled}
                    aria-label={`Toggle policy ${policy.name}`}
                    onClick={(event) => event.stopPropagation()}
                    onChange={() => toggleEnabled(policy.id)}
                  />
                </button>
              ))
            )}
          </div>
        </section>

        <section className="policies-editor">
          {!draft ? (
            <div className="card">
              <div className="empty">Select a policy to edit.</div>
            </div>
          ) : (
            <div className="policies-editor-stack">
              <div className="card">
                <div className="policies-editor-head">
                  <div>
                    <div className="card-title">Editor</div>
                    <div className="control-hint">
                      {unsaved ? "Unsaved changes" : `Saved v${draft.version}`}
                    </div>
                  </div>
                  <div className="policies-editor-actions">
                    <button type="button" className="button outline" onClick={doDuplicate}>
                      Duplicate
                    </button>
                    <button type="button" className="button ghost" onClick={doDelete}>
                      Delete
                    </button>
                    <button
                      type="button"
                      className="button outline"
                      onClick={runPolicyNow}
                      disabled={!draft || errors.length > 0 || runBusy}
                      title={errors.length > 0 ? "Fix validation errors to run" : "Run policy"}
                    >
                      {runBusy ? "Running..." : "Run now"}
                    </button>
                    <button
                      type="button"
                      className="button primary"
                      onClick={doSave}
                      disabled={errors.length > 0}
                       title={errors.length > 0 ? "Fix validation errors to save" : "Save"}
                     >
                       Save
                     </button>
                  </div>
                </div>

                <div className="policy-form">
                  <div className="policy-form-row">
                    <div className="policy-field">
                      <label htmlFor="policyName">Name</label>
                      <input
                        id="policyName"
                        value={draft.name}
                        onChange={(event) => updateDraft({ name: event.target.value })}
                      />
                    </div>
                    <div className="policy-field">
                      <label htmlFor="policyStatusEdit">Status</label>
                      <select
                        id="policyStatusEdit"
                        value={draft.status}
                        onChange={(event) =>
                          updateDraft({ status: event.target.value as PolicyStatus })
                        }
                      >
                        <option value="draft">draft</option>
                        <option value="active">active</option>
                        <option value="archived">archived</option>
                      </select>
                    </div>
                    <div className="policy-field">
                      <label htmlFor="policyEnabled">Enabled</label>
                      <select
                        id="policyEnabled"
                        value={draft.enabled ? "on" : "off"}
                        onChange={(event) =>
                          updateDraft({ enabled: event.target.value === "on" })
                        }
                      >
                        <option value="off">off</option>
                        <option value="on">on</option>
                      </select>
                    </div>
                  </div>

                  <div className="policy-form-row">
                    <div className="policy-field">
                      <label htmlFor="policyModeEdit">Mode</label>
                      <select
                        id="policyModeEdit"
                        value={draft.mode}
                        onChange={(event) =>
                          updateDraft({ mode: event.target.value as PolicyMode })
                        }
                      >
                        <option value="ADVISE_ONLY">ADVISE_ONLY</option>
                        <option value="AUTO_EXECUTE">AUTO_EXECUTE</option>
                      </select>
                    </div>
                    <div className="policy-field">
                      <label htmlFor="policyPriority">Priority</label>
                      <input
                        id="policyPriority"
                        type="number"
                        min={0}
                        value={draft.priority}
                        onChange={(event) =>
                          updateDraft({ priority: Number(event.target.value) })
                        }
                      />
                    </div>
                    <div className="policy-field">
                      <label htmlFor="policyVersion">Version</label>
                      <input id="policyVersion" value={`v${draft.version}`} readOnly />
                    </div>
                  </div>

                  <div className="policy-field">
                    <label htmlFor="policyNotes">Notes</label>
                    <textarea
                      id="policyNotes"
                      value={draft.notes ?? ""}
                      onChange={(event) => updateDraft({ notes: event.target.value })}
                      rows={2}
                    />
                  </div>

                  <div className="policy-section">
                    <div className="policy-section-title">Scope</div>
                    <div className="policy-form-row">
                      <div className="policy-field">
                        <label htmlFor="policyScope">Scope type</label>
                        <select
                          id="policyScope"
                          value={draft.scope.type}
                          onChange={(event) => {
                            const nextType = event.target.value as Policy["scope"]["type"];
                            if (nextType === "nodes") {
                              updateDraft({ scope: { type: "nodes", nodeIds: [] } });
                              return;
                            }
                            if (nextType === "all") {
                              updateDraft({ scope: { type: "all" } });
                              return;
                            }
                            // tag/group reserved
                          }}
                        >
                          <option value="all">all</option>
                          <option value="nodes">nodes</option>
                          <option value="tag" disabled>
                            tag (future)
                          </option>
                          <option value="group" disabled>
                            group (future)
                          </option>
                        </select>
                      </div>

                      {draft.scope.type === "nodes" ? (
                        <div className="policy-field policy-field-wide">
                          <label htmlFor="policyNodeIds">Node ids</label>
                          <input
                            id="policyNodeIds"
                            value={stringifyNodeIds(draft.scope.nodeIds ?? [])}
                            onChange={(event) => updateScopeNodes(event.target.value)}
                            placeholder="S1, S2, ..."
                          />
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div className="policy-section">
                    <div className="policy-section-title">Conditions</div>
                    <div className="control-hint">MVP supports AND only. Duration preview is snapshot-based.</div>

                    <div className="policy-listing">
                      {draft.conditions.items.length === 0 ? (
                        <div className="empty">No conditions yet.</div>
                      ) : (
                        draft.conditions.items.map((condition, idx) => (
                          <div key={idx} className="policy-line">
                            <select
                              value={condition.metric}
                              onChange={(event) =>
                                updateCondition(idx, {
                                  metric: event.target.value as ConditionMetric
                                })
                              }
                            >
                              <option value="temp">temp</option>
                              <option value="load">load</option>
                              <option value="error_rate">error_rate</option>
                              <option value="health">health</option>
                            </select>
                            <select
                              value={condition.op}
                              onChange={(event) =>
                                updateCondition(idx, { op: event.target.value as ConditionOp })
                              }
                            >
                              <option value=">">&gt;</option>
                              <option value=">=">&gt;=</option>
                              <option value="<">&lt;</option>
                              <option value="<=">&lt;=</option>
                            </select>
                            <input
                              type="number"
                              value={condition.value}
                              onChange={(event) =>
                                updateCondition(idx, { value: Number(event.target.value) })
                              }
                            />
                            <input
                              type="number"
                              min={0}
                              value={condition.durationSec ?? 0}
                              onChange={(event) =>
                                updateCondition(idx, {
                                  durationSec: Number(event.target.value)
                                })
                              }
                              title="duration (sec)"
                            />
                            <button
                              type="button"
                              className="button ghost"
                              onClick={() => removeCondition(idx)}
                            >
                              Remove
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                    <button type="button" className="button outline" onClick={addCondition}>
                      Add condition
                    </button>
                  </div>

                  <div className="policy-section">
                    <div className="policy-section-title">Actions</div>
                    <div className="policy-listing">
                      {draft.actions.length === 0 ? (
                        <div className="empty">No actions yet.</div>
                      ) : (
                        draft.actions.map((action, idx) => (
                          <div key={idx} className="policy-line">
                            <select
                              value={action.type}
                              onChange={(event) => {
                                const nextType = event.target.value as ActionType;
                                const catalog = getActionCatalogItem(nextType);
                                if (!catalog) return;
                                const providerAllows = catalog.capability !== "probe";
                                if (!providerAllows) return;
                                updateAction(idx, {
                                  type: nextType,
                                  capability: catalog.capability,
                                  availability: catalog.availability
                                });
                              }}
                            >
                              {getAvailableActions().map((item) => {
                                const providerAllows = item.capability !== "probe";
                                const label = item.availability === "future" ? `${item.label} (future)` : item.label;
                                return (
                                  <option key={item.type} value={item.type} disabled={!providerAllows}>
                                    {label}
                                  </option>
                                );
                              })}
                            </select>
                            <span className="policy-chip">risk {computeRiskLevel([action])}</span>
                            <button type="button" className="button ghost" onClick={() => moveAction(idx, -1)}>
                              Up
                            </button>
                            <button type="button" className="button ghost" onClick={() => moveAction(idx, 1)}>
                              Down
                            </button>
                            <button type="button" className="button ghost" onClick={() => removeAction(idx)}>
                              Remove
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                    <button type="button" className="button outline" onClick={addAction}>
                      Add action
                    </button>
                  </div>

                  <div className="policy-section">
                    <div className="policy-section-title">Guardrails</div>
                    <div className="policy-form-row">
                      <div className="policy-field">
                        <label htmlFor="policyCooldown">Cooldown (sec)</label>
                        <input
                          id="policyCooldown"
                          type="number"
                          min={0}
                          value={draft.guardrails.cooldownSec}
                          onChange={(event) =>
                            updateDraft({
                              guardrails: {
                                ...draft.guardrails,
                                cooldownSec: Number(event.target.value)
                              }
                            })
                          }
                        />
                      </div>
                      <div className="policy-field">
                        <label htmlFor="policyMax">Max/hour</label>
                        <input
                          id="policyMax"
                          type="number"
                          min={0}
                          value={draft.guardrails.maxPerHour}
                          onChange={(event) =>
                            updateDraft({
                              guardrails: {
                                ...draft.guardrails,
                                maxPerHour: Number(event.target.value)
                              }
                            })
                          }
                        />
                      </div>
                      <div className="policy-field">
                        <label htmlFor="policyApproval">Require approval</label>
                        <select
                          id="policyApproval"
                          value={draft.guardrails.requireApproval ? "on" : "off"}
                          onChange={(event) =>
                            updateDraft({
                              guardrails: {
                                ...draft.guardrails,
                                requireApproval: event.target.value === "on"
                              }
                            })
                          }
                        >
                          <option value="off">off</option>
                          <option value="on">on</option>
                        </select>
                        {draft.mode === "AUTO_EXECUTE" && derivedRisk >= 2 ? (
                          <div className="control-hint">
                            Recommended for risk level {derivedRisk} in AUTO_EXECUTE.
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>

                {errors.length > 0 ? (
                  <div className="policy-errors">
                    <div className="policy-errors-title">Validation</div>
                    <ul>
                      {errors.map((err) => (
                        <li key={err}>{err}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {runError ? <div className="policy-errors">{runError}</div> : null}
              </div>
            </div>

              <div className="card">
                <div className="card-title">Preview</div>
                <div className="payload-grid">
                  <div>
                    <div className="payload-label">Match</div>
                    <div>{matchPreview.matched.length} nodes</div>
                  </div>
                  <div>
                    <div className="payload-label">Risk</div>
                    <div className={`severity-badge severity-${derivedRisk >= 2 ? "high" : "low"}`}>
                      level {derivedRisk}
                    </div>
                  </div>
                  <div>
                    <div className="payload-label">Require approval</div>
                    <div>{draft.guardrails.requireApproval ? "yes" : "no"}</div>
                  </div>
                </div>

                {matchPreview.unsupportedDuration ? (
                  <div className="control-hint">
                    Duration conditions require history. Match preview uses current snapshot only.
                  </div>
                ) : null}

                <div className="policy-preview-block">
                  <div className="payload-label">Matched nodes</div>
                  {matchPreview.matched.length === 0 ? (
                    <div className="empty">No nodes match current conditions.</div>
                  ) : (
                    <div className="policy-preview-list">
                      {matchPreview.matched.slice(0, 50).map((nodeId) => (
                        <span key={nodeId} className="policy-chip policy-chip-mono">
                          {nodeId}
                        </span>
                      ))}
                      {matchPreview.matched.length > 50 ? (
                        <span className="control-hint">+{matchPreview.matched.length - 50} more</span>
                      ) : null}
                    </div>
                  )}
                </div>

                <div className="policy-preview-block">
                  <div className="payload-label">Actions</div>
                  {draft.actions.length === 0 ? (
                    <div className="empty">No actions defined.</div>
                  ) : (
                    <div className="policy-preview-actions">
                      {draft.actions.map((action, idx) => (
                        <span key={`${action.type}-${idx}`} className="policy-chip">
                          {formatActionLabel(action.type)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
