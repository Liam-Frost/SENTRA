import { useEffect, useMemo, useState } from "react";

import { listNodes, type Node } from "../api/infrastructure";
import {
  createOperationTemplate,
  deleteOperationTemplate,
  executeOperationTemplate,
  getOperationExecution,
  listOperationExecutions,
  listOperationTemplates,
  updateOperationTemplate,
  type OperationExecution,
  type OperationExecutionDetail,
  type OperationTemplate,
  type OperationTemplateStep
} from "../api/operationTemplates";
import { cancelOperation } from "../api/operations";
import { formatDateTime } from "../utils/format";

type TemplateDraft = {
  name: string;
  description: string;
  steps: OperationTemplateStep[];
};

type OverlayMode = "create" | "edit" | null;

const EMPTY_STEP = (position: number): OperationTemplateStep => ({
  position,
  name: `Step ${position}`,
  command: "",
  timeoutSec: 60,
  continueOnError: false
});

const EMPTY_TEMPLATE: TemplateDraft = {
  name: "",
  description: "",
  steps: [EMPTY_STEP(1)]
};

function sortSteps(steps: OperationTemplateStep[]) {
  return steps.map((step, index) => ({ ...step, position: index + 1 }));
}

function buildDraft(template: OperationTemplate | null): TemplateDraft {
  if (!template) return EMPTY_TEMPLATE;
  return {
    name: template.name,
    description: template.description || "",
    steps: template.steps.map((step) => ({ ...step }))
  };
}

export default function OperationsPage() {
  const [templates, setTemplates] = useState<OperationTemplate[]>([]);
  const [executions, setExecutions] = useState<OperationExecution[]>([]);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [executionDetail, setExecutionDetail] = useState<OperationExecutionDetail | null>(null);
  const [draft, setDraft] = useState<TemplateDraft>(EMPTY_TEMPLATE);
  const [selectedTargets, setSelectedTargets] = useState<string[]>([]);
  const [overlayMode, setOverlayMode] = useState<OverlayMode>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspace = async () => {
    setLoading(true);
    try {
      const [templateData, executionData, nodeData] = await Promise.all([
        listOperationTemplates(),
        listOperationExecutions({ source: "manual", limit: 24 }),
        listNodes()
      ]);
      setTemplates(Array.isArray(templateData.templates) ? templateData.templates : []);
      setExecutions(Array.isArray(executionData.executions) ? executionData.executions : []);
      setNodes(Array.isArray(nodeData.nodes) ? nodeData.nodes : []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load operations workspace");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkspace();
  }, []);

  const filteredTemplates = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return templates;
    return templates.filter((template) => {
      const hay = `${template.name} ${template.description ?? ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [query, templates]);

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedTemplateId) ?? null,
    [templates, selectedTemplateId]
  );

  useEffect(() => {
    if (!selectedExecutionId) {
      setExecutionDetail(null);
      return;
    }
    const loadDetail = async () => {
      try {
        const detail = await getOperationExecution(selectedExecutionId);
        setExecutionDetail(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load execution detail");
      }
    };
    loadDetail();
  }, [selectedExecutionId]);

  const openCreate = () => {
    setDraft(EMPTY_TEMPLATE);
    setOverlayMode("create");
    setError(null);
  };

  const openEdit = (template: OperationTemplate) => {
    setSelectedTemplateId(template.id);
    setDraft(buildDraft(template));
    setOverlayMode("edit");
    setSelectedExecutionId(null);
    setExecutionDetail(null);
    setError(null);
  };

  const closeOverlay = () => {
    setOverlayMode(null);
    setSelectedTemplateId(null);
    setSelectedExecutionId(null);
    setExecutionDetail(null);
    setSelectedTargets([]);
  };

  const updateStep = (index: number, patch: Partial<OperationTemplateStep>) => {
    setDraft((current) => ({
      ...current,
      steps: current.steps.map((step, stepIndex) =>
        stepIndex === index ? { ...step, ...patch } : step
      )
    }));
  };

  const addStep = () => {
    setDraft((current) => ({
      ...current,
      steps: [...current.steps, EMPTY_STEP(current.steps.length + 1)]
    }));
  };

  const removeStep = (index: number) => {
    setDraft((current) => {
      const next = current.steps.filter((_, stepIndex) => stepIndex !== index);
      return {
        ...current,
        steps: sortSteps(next.length > 0 ? next : [EMPTY_STEP(1)])
      };
    });
  };

  const moveStep = (index: number, direction: -1 | 1) => {
    setDraft((current) => {
      const next = [...current.steps];
      const targetIndex = index + direction;
      if (targetIndex < 0 || targetIndex >= next.length) return current;
      [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
      return { ...current, steps: sortSteps(next) };
    });
  };

  const saveTemplate = async () => {
    if (!draft.name.trim()) {
      setError("Template name is required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: draft.name.trim(),
        description: draft.description.trim(),
        steps: sortSteps(draft.steps).map((step) => ({
          position: step.position,
          name: step.name.trim() || `Step ${step.position}`,
          command: step.command,
          timeoutSec: Number(step.timeoutSec) || 60,
          continueOnError: Boolean(step.continueOnError)
        }))
      };
      if (overlayMode === "create") {
        await createOperationTemplate(payload);
      } else if (overlayMode === "edit" && selectedTemplateId) {
        await updateOperationTemplate(selectedTemplateId, payload);
      }
      await loadWorkspace();
      closeOverlay();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save template");
    } finally {
      setSaving(false);
    }
  };

  const removeSelectedTemplate = async () => {
    if (!selectedTemplateId) return;
    setSaving(true);
    try {
      await deleteOperationTemplate(selectedTemplateId);
      await loadWorkspace();
      closeOverlay();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete template");
    } finally {
      setSaving(false);
    }
  };

  const toggleTarget = (nodeId: string) => {
    setSelectedTargets((current) =>
      current.includes(nodeId) ? current.filter((value) => value !== nodeId) : [...current, nodeId]
    );
  };

  const runTemplate = async () => {
    if (!selectedTemplateId) {
      setError("Select a template first");
      return;
    }
    if (selectedTargets.length === 0) {
      setError("Select at least one node");
      return;
    }
    setSaving(true);
    try {
      const created = await executeOperationTemplate(selectedTemplateId, {
        targets: selectedTargets,
        initiator: "panel"
      });
      const detail = await getOperationExecution(created.execution.id);
      setSelectedExecutionId(created.execution.id);
      setExecutionDetail(detail);
      await loadWorkspace();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run template");
    } finally {
      setSaving(false);
    }
  };

  const cancelSelectedExecution = async () => {
    if (!selectedExecutionId) return;
    setSaving(true);
    try {
      await cancelOperation(selectedExecutionId);
      const detail = await getOperationExecution(selectedExecutionId);
      setExecutionDetail(detail);
      await loadWorkspace();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel execution");
    } finally {
      setSaving(false);
    }
  };

  const templateExecutions = useMemo(() => {
    if (!selectedTemplateId) return [];
    return executions.filter((execution) => execution.templateId === selectedTemplateId);
  }, [executions, selectedTemplateId]);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Automation</div>
          <h2 className="page-title">Operations</h2>
        </div>
        <div className="page-actions">
          <div className="status-chip">Templates {templates.length}</div>
          <button type="button" className="button primary" onClick={openCreate}>Add template</button>
        </div>
      </div>

      {error ? (
        <div className="alert"><strong>Error:</strong> {error}</div>
      ) : null}

      <section className="card library-page-card">
        <div className="library-page-head">
          <div>
            <div className="card-title">Operation template library</div>
            <div className="control-hint">Templates stay here. Editing, targeting, and execution happen after you open one.</div>
          </div>
        </div>

        <div className="fleet-search">
          <label htmlFor="operationSearch">Search</label>
          <input
            id="operationSearch"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="template name or description"
          />
        </div>

        {loading ? <div className="empty">Loading templates...</div> : null}
        {!loading && filteredTemplates.length === 0 ? <div className="empty">No templates found.</div> : null}

        {!loading && filteredTemplates.length > 0 ? (
          <div className="library-grid">
            {filteredTemplates.map((template) => (
              <button key={template.id} type="button" className="library-card" onClick={() => openEdit(template)}>
                <div className="library-card-head">
                  <div className="library-card-title">{template.name}</div>
                  <span className="severity-badge severity-low">{template.steps.length} steps</span>
                </div>
                <div className="library-card-meta">Updated {formatDateTime(template.updatedAt)}</div>
                <div className="library-card-description">{template.description || "No description yet."}</div>
              </button>
            ))}
          </div>
        ) : null}
      </section>

      {overlayMode ? (
        <div className="overlay-shell" role="presentation" onClick={closeOverlay}>
          <div className="overlay-panel" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
            <div className="overlay-head">
              <div>
                <div className="card-title">{overlayMode === "create" ? "Create template" : selectedTemplate?.name || "Template detail"}</div>
              </div>
              <button type="button" className="button outline" onClick={closeOverlay}>Close</button>
            </div>
            <div className="overlay-body">
              {overlayMode === "edit" && selectedTemplate ? (
                <div className="payload-grid">
                  <div>
                    <div className="payload-label">Template ID</div>
                    <div className="fleet-mono">{selectedTemplate.id}</div>
                  </div>
                  <div>
                    <div className="payload-label">Step count</div>
                    <div>{selectedTemplate.steps.length}</div>
                  </div>
                  <div>
                    <div className="payload-label">Updated</div>
                    <div>{formatDateTime(selectedTemplate.updatedAt)}</div>
                  </div>
                </div>
              ) : null}

              <div className="operation-template-form">
                <div className="operation-template-field">
                  <label htmlFor="templateName">Name</label>
                  <input
                    id="templateName"
                    value={draft.name}
                    onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Restart application services"
                  />
                </div>

                <div className="operation-template-field">
                  <label htmlFor="templateDescription">Description</label>
                  <textarea
                    id="templateDescription"
                    value={draft.description}
                    onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
                    rows={3}
                    placeholder="Explain when this template should be used"
                  />
                </div>

                <div className="operation-template-steps-head">
                  <div className="card-title">Steps</div>
                  <button type="button" className="button outline" onClick={addStep}>Add step</button>
                </div>

                <div className="operation-template-step-list">
                  {draft.steps.map((step, index) => (
                    <div key={`${step.position}-${index}`} className="operation-template-step-card">
                      <div className="operation-template-step-top">
                        <strong>Step {index + 1}</strong>
                        <div className="operations-actions">
                          <button type="button" className="button outline" onClick={() => moveStep(index, -1)}>Up</button>
                          <button type="button" className="button outline" onClick={() => moveStep(index, 1)}>Down</button>
                          <button type="button" className="button outline" onClick={() => removeStep(index)}>Remove</button>
                        </div>
                      </div>

                      <div className="operation-template-step-grid">
                        <div className="operation-template-field">
                          <label>Name</label>
                          <input value={step.name} onChange={(event) => updateStep(index, { name: event.target.value })} />
                        </div>
                        <div className="operation-template-field">
                          <label>Timeout (sec)</label>
                          <input
                            type="number"
                            min={1}
                            value={step.timeoutSec}
                            onChange={(event) => updateStep(index, { timeoutSec: Number(event.target.value) || 60 })}
                          />
                        </div>
                      </div>

                      <div className="operation-template-field">
                        <label>Shell command</label>
                        <textarea
                          value={step.command}
                          onChange={(event) => updateStep(index, { command: event.target.value })}
                          rows={4}
                          placeholder="systemctl restart my-service"
                        />
                      </div>

                      <label className="action-field-inline">
                        <input
                          type="checkbox"
                          checked={step.continueOnError}
                          onChange={(event) => updateStep(index, { continueOnError: event.target.checked })}
                        />
                        <span>Continue on error</span>
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {overlayMode === "edit" && selectedTemplate ? (
                <>
                  <div className="overlay-section">
                    <div className="operations-panel-head">
                      <div>
                        <div className="card-title">Run template</div>
                        <div className="control-hint">Select nodes and queue a run from here.</div>
                      </div>
                    </div>
                    <div className="operations-v2-node-grid">
                      {nodes.map((node) => (
                        <label key={node.id} className={`operations-v2-node ${selectedTargets.includes(node.id) ? "selected" : ""}`.trim()}>
                          <input type="checkbox" checked={selectedTargets.includes(node.id)} onChange={() => toggleTarget(node.id)} />
                          <span>{node.hostname}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div className="overlay-section">
                    <div className="card-title">Recent executions</div>
                    {templateExecutions.length === 0 ? (
                      <div className="empty">No executions for this template yet.</div>
                    ) : (
                      <div className="operations-execution-layout">
                        <div className="command-list">
                          {templateExecutions.map((execution) => (
                            <button
                              key={execution.id}
                              type="button"
                              className={`command-row ${selectedExecutionId === execution.id ? "active" : ""}`.trim()}
                              onClick={() => setSelectedExecutionId(execution.id)}
                            >
                              <div className="command-row-main">
                                <div className="command-row-title">{formatDateTime(execution.createdAt)}</div>
                                <div className="command-row-meta">{execution.targets.length} nodes</div>
                              </div>
                              <span className={`severity-badge severity-${execution.status}`}>{execution.status}</span>
                            </button>
                          ))}
                        </div>

                        <div className="operations-execution-detail-card">
                          {!executionDetail ? (
                            <div className="empty">Select an execution to inspect it.</div>
                          ) : (
                            <>
                              <div className="operations-panel-head">
                                <div>
                                  <div className="card-title">Execution detail</div>
                                  <div className="control-hint">Node output and logs for this run.</div>
                                </div>
                                <button type="button" className="button outline" disabled={saving} onClick={cancelSelectedExecution}>Cancel</button>
                              </div>

                              <div className="command-runs">
                                <div className="command-runs-head">
                                  <span>Node</span>
                                  <span>Status</span>
                                  <span>Output</span>
                                </div>
                                {executionDetail.runs.map((run) => (
                                  <div key={run.id} className="command-runs-row">
                                    <span className="fleet-mono">{run.nodeId ?? "fleet"}</span>
                                    <span>{run.status}</span>
                                    <span>{run.output ?? "-"}</span>
                                  </div>
                                ))}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </>
              ) : null}

              <div className="overlay-actions">
                {overlayMode === "edit" && selectedTemplate ? (
                  <button type="button" className="button outline" disabled={saving} onClick={removeSelectedTemplate}>Delete</button>
                ) : null}
                <div className="spacer" />
                {overlayMode === "edit" && selectedTemplate ? (
                  <button type="button" className="button outline" disabled={saving} onClick={runTemplate}>Run template</button>
                ) : null}
                <button type="button" className="button primary" disabled={saving} onClick={saveTemplate}>
                  {saving ? "Saving..." : overlayMode === "create" ? "Create template" : "Save changes"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
