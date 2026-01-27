import { useState, useMemo } from "react";
import type { Action } from "../api/actions";
import { getActionReferences } from "../api/actions";
import {
  useActionStore,
  createAction,
  updateAction,
  deleteAction,
  duplicateAction,
} from "../state/actionStore";

type ActionFilter = {
  showSystem: boolean;
  showCustom: boolean;
  availability: "all" | "available" | "future" | "deprecated";
  capability: "all" | "simulation" | "probe" | "both";
  category: string;
};

export default function Actions() {
  const { actions, loading } = useActionStore();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<ActionFilter>({
    showSystem: true,
    showCustom: true,
    availability: "all",
    capability: "all",
    category: "all",
  });
  const [editData, setEditData] = useState<Partial<Action> | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const selectedAction = useMemo(() => {
    return actions.find((a) => a.id === selectedId) ?? null;
  }, [actions, selectedId]);

  const filteredActions = useMemo(() => {
    return actions.filter((action) => {
      if (!filter.showSystem && action.isSystem) return false;
      if (!filter.showCustom && !action.isSystem) return false;
      if (filter.availability !== "all" && action.availability !== filter.availability)
        return false;
      if (filter.capability !== "all" && action.capability !== filter.capability) {
        if (action.capability !== "both") return false;
      }
      if (filter.category !== "all" && action.category !== filter.category) return false;
      return true;
    });
  }, [actions, filter]);

  const categories = useMemo(() => {
    const cats = new Set<string>();
    actions.forEach((a) => {
      if (a.category) cats.add(a.category);
    });
    return ["all", ...Array.from(cats).sort()];
  }, [actions]);

  const handleCreate = () => {
    setIsCreating(true);
    setSelectedId(null);
    setEditData({
      id: "",
      label: "",
      category: "custom",
      capability: "probe",
      availability: "available",
      riskLevel: 1,
      requiresTarget: true,
      description: "",
      parametersSchema: "",
      defaultParameters: "",
    });
    setError(null);
  };

  const handleSelect = (action: Action) => {
    setIsCreating(false);
    setSelectedId(action.id);
    setEditData({ ...action });
    setError(null);
  };

  const handleSave = async () => {
    if (!editData) return;

    setError(null);
    setSaving(true);

    try {
      if (isCreating) {
        if (!editData.id || !editData.label) {
          setError("ID and Label are required");
          setSaving(false);
          return;
        }
        const created = await createAction(editData);
        setSelectedId(created.id);
        setIsCreating(false);
        setEditData({ ...created });
      } else if (selectedId) {
        const updated = await updateAction(selectedId, editData);
        setEditData({ ...updated });
      }
    } catch (err: any) {
      setError(err.message || "Failed to save action");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedId) return;
    
    const action = actions.find((a) => a.id === selectedId);
    if (!action) return;

    if (action.isSystem) {
      setError("Cannot delete system actions");
      return;
    }

    // Check references
    try {
      const refs = await getActionReferences(selectedId);
      const policyCount = refs.policies.length;
      const opCount = refs.operations.length;

      if (policyCount > 0 || opCount > 0) {
        const parts = [];
        if (policyCount > 0)
          parts.push(`${policyCount} ${policyCount === 1 ? "policy" : "policies"}`);
        if (opCount > 0)
          parts.push(`${opCount} pending ${opCount === 1 ? "operation" : "operations"}`);
        setError(`Cannot delete: used by ${parts.join(" and ")}`);
        return;
      }

      if (!confirm(`Delete action "${action.label}"?`)) return;

      setError(null);
      await deleteAction(selectedId);
      setSelectedId(null);
      setEditData(null);
    } catch (err: any) {
      setError(err.message || "Failed to delete action");
    }
  };

  const handleDuplicate = async () => {
    if (!selectedId) return;

    try {
      const duplicated = await duplicateAction(selectedId);
      if (duplicated) {
        setSelectedId(duplicated.id);
        setEditData({ ...duplicated });
      }
    } catch (err: any) {
      setError(err.message || "Failed to duplicate action");
    }
  };

  const isSystemAction = selectedAction?.isSystem ?? false;
  const canEdit = !isSystemAction || (isSystemAction && editData);
  const canDelete = !isSystemAction && !isCreating;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-eyebrow">Configuration</div>
          <h2 className="page-title">Actions</h2>
          <p className="page-description">
            Manage actions that can be executed on nodes manually or by policies.
          </p>
        </div>
        <div className="page-actions">
          <button className="button primary" onClick={handleCreate}>
            + New Action
          </button>
        </div>
      </div>

      <div className="actions-container">
        <div className="actions-list">
          <div className="actions-filters">
            <div className="actions-filters-title">Filters</div>
            
            <div className="filter-group">
              <span className="filter-group-label">Type</span>
              <label className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={filter.showSystem}
                  onChange={(e) => setFilter({ ...filter, showSystem: e.target.checked })}
                />
                <span>System</span>
              </label>
              <label className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={filter.showCustom}
                  onChange={(e) => setFilter({ ...filter, showCustom: e.target.checked })}
                />
                <span>Custom</span>
              </label>
            </div>

            <div className="filter-group">
              <span className="filter-group-label">Availability</span>
              <select
                value={filter.availability}
                onChange={(e) =>
                  setFilter({
                    ...filter,
                    availability: e.target.value as ActionFilter["availability"],
                  })
                }
              >
                <option value="all">All</option>
                <option value="available">Available</option>
                <option value="future">Future</option>
                <option value="deprecated">Deprecated</option>
              </select>
            </div>

            <div className="filter-group">
              <span className="filter-group-label">Capability</span>
              <select
                value={filter.capability}
                onChange={(e) =>
                  setFilter({
                    ...filter,
                    capability: e.target.value as ActionFilter["capability"],
                  })
                }
              >
                <option value="all">All</option>
                <option value="simulation">Simulation</option>
                <option value="probe">Probe</option>
                <option value="both">Both</option>
              </select>
            </div>

            <div className="filter-group">
              <span className="filter-group-label">Category</span>
              <select
                value={filter.category}
                onChange={(e) => setFilter({ ...filter, category: e.target.value })}
              >
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat === "all" ? "All" : cat}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="actions-list-items">
            {loading && (
              <div className="action-row">
                <div className="action-row-title">Loading...</div>
              </div>
            )}
            {!loading && filteredActions.length === 0 && (
              <div className="action-row">
                <div className="action-row-title">No actions match filters</div>
              </div>
            )}
            {filteredActions.map((action) => (
              <div
                key={action.id}
                className={`action-row ${selectedId === action.id ? "active" : ""}`}
                onClick={() => handleSelect(action)}
              >
                <div className="action-row-title">{action.label}</div>
                <div className="action-row-meta">
                  {action.isSystem && <span className="badge badge-system">System</span>}
                  <span className="badge badge-capability">{action.capability}</span>
                  <span className={`badge badge-risk-${action.riskLevel}`}>
                    Risk {action.riskLevel}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="actions-editor">
          {!editData && !selectedId && (
            <div className="actions-editor-empty">
              <div>
                <p>Select an action to view details or create a new one.</p>
              </div>
            </div>
          )}

          {editData && (
            <div className="action-form">
              <div className="action-form-header">
                <h3 className="action-form-title">
                  {isCreating ? "New Action" : selectedAction?.label}
                </h3>
                {selectedAction && (
                  <div className="action-form-subtitle">
                    {selectedAction.isSystem ? "System Action" : "Custom Action"} • ID: {selectedAction.id}
                  </div>
                )}
              </div>

              {error && <div className="alert alert-error">{error}</div>}

              <div className="action-form-section">
                <div className="action-form-section-title">Basic Information</div>

                <div className="action-field">
                  <label>ID *</label>
                  <input
                    type="text"
                    value={editData.id || ""}
                    onChange={(e) => setEditData({ ...editData, id: e.target.value })}
                    disabled={!isCreating}
                    placeholder="action_id_lowercase"
                  />
                  <small>Alphanumeric and underscores only. Cannot be changed after creation.</small>
                </div>

                <div className="action-field">
                  <label>Label *</label>
                  <input
                    type="text"
                    value={editData.label || ""}
                    onChange={(e) => setEditData({ ...editData, label: e.target.value })}
                    disabled={!canEdit}
                    placeholder="Human-readable name"
                  />
                </div>

                <div className="action-field">
                  <label>Description</label>
                  <textarea
                    value={editData.description || ""}
                    onChange={(e) => setEditData({ ...editData, description: e.target.value })}
                    disabled={!canEdit}
                    rows={3}
                    placeholder="Describe what this action does"
                  />
                </div>
              </div>

              <div className="action-form-section">
                <div className="action-form-section-title">Configuration</div>

                <div className="action-field-row">
                  <div className="action-field">
                    <label>Category</label>
                    <select
                      value={editData.category || ""}
                      onChange={(e) => setEditData({ ...editData, category: e.target.value })}
                      disabled={isSystemAction}
                    >
                      <option value="">None</option>
                      <option value="cooling">Cooling</option>
                      <option value="routing">Routing</option>
                      <option value="lifecycle">Lifecycle</option>
                      <option value="diagnostics">Diagnostics</option>
                      <option value="custom">Custom</option>
                    </select>
                  </div>

                  <div className="action-field">
                    <label>Capability *</label>
                    <select
                      value={editData.capability || "probe"}
                      onChange={(e) =>
                        setEditData({
                          ...editData,
                          capability: e.target.value as Action["capability"],
                        })
                      }
                      disabled={isSystemAction}
                    >
                      <option value="simulation">Simulation</option>
                      <option value="probe">Probe</option>
                      <option value="both">Both</option>
                    </select>
                  </div>
                </div>

                <div className="action-field-row">
                  <div className="action-field">
                    <label>Availability *</label>
                    <select
                      value={editData.availability || "available"}
                      onChange={(e) =>
                        setEditData({
                          ...editData,
                          availability: e.target.value as Action["availability"],
                        })
                      }
                      disabled={isSystemAction}
                    >
                      <option value="available">Available</option>
                      <option value="future">Future</option>
                      <option value="deprecated">Deprecated</option>
                    </select>
                  </div>

                  <div className="action-field">
                    <label>Risk Level *</label>
                    <select
                      value={editData.riskLevel ?? 1}
                      onChange={(e) =>
                        setEditData({ ...editData, riskLevel: parseInt(e.target.value) })
                      }
                      disabled={isSystemAction}
                    >
                      <option value={0}>0 - Safe</option>
                      <option value={1}>1 - Low</option>
                      <option value={2}>2 - Medium</option>
                      <option value={3}>3 - High</option>
                    </select>
                  </div>
                </div>

                <div className="action-field">
                  <label className="action-field-inline">
                    <input
                      type="checkbox"
                      checked={editData.requiresTarget ?? true}
                      onChange={(e) =>
                        setEditData({ ...editData, requiresTarget: e.target.checked })
                      }
                      disabled={isSystemAction}
                    />
                    <span>Requires Target Node</span>
                  </label>
                </div>
              </div>

              <div className="action-form-section">
                <div className="action-form-section-title">Advanced</div>

                <div className="action-field">
                  <label>Parameters Schema (JSON)</label>
                  <textarea
                    value={editData.parametersSchema || ""}
                    onChange={(e) =>
                      setEditData({ ...editData, parametersSchema: e.target.value })
                    }
                    disabled={isSystemAction}
                    rows={8}
                    placeholder='{"type": "object", "properties": {...}}'
                    style={{ fontFamily: "monospace", fontSize: "0.9em" }}
                  />
                  <small>JSON Schema for action parameters (optional)</small>
                </div>
              </div>

              <div className="action-form-actions">
                {canDelete && (
                  <button className="button danger" onClick={handleDelete}>
                    Delete
                  </button>
                )}
                {!isCreating && canDelete && (
                  <button className="button outline" onClick={handleDuplicate}>
                    Duplicate
                  </button>
                )}
                <div className="spacer" />
                <button
                  className="button primary"
                  onClick={handleSave}
                  disabled={saving || !canEdit}
                >
                  {saving ? "Saving..." : isCreating ? "Create" : "Save"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
