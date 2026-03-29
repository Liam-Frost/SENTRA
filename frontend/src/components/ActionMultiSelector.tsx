import { useState, useMemo } from "react";
import { useActionStore } from "../state/actionStore";
import type { Action } from "../api/actions";

type ActionMultiSelectorProps = {
  mode: "simulation" | "probe";
  onExecute: (actionIds: string[]) => void;
  disabled?: boolean;
};

export default function ActionMultiSelector({
  mode,
  onExecute,
  disabled = false,
}: ActionMultiSelectorProps) {
  const { actions } = useActionStore();
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const availableActions = useMemo(() => {
    return actions.filter((action) => {
      if (action.availability !== "available") return false;
      
      // Filter by capability
      if (action.capability === "both") return true;
      if (mode === "simulation") {
        return action.capability === "simulation";
      } else {
        return action.capability === "probe";
      }
    });
  }, [actions, mode]);

  // Group actions by category
  const groupedActions = useMemo(() => {
    const groups: Record<string, Action[]> = {};
    
    availableActions.forEach((action) => {
      const category = action.category || "other";
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(action);
    });
    
    return groups;
  }, [availableActions]);

  const categories = Object.keys(groupedActions).sort();

  const handleToggle = (actionId: string) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(actionId)) {
      newSelected.delete(actionId);
    } else {
      newSelected.add(actionId);
    }
    setSelectedIds(newSelected);
  };

  const handleSelectAll = () => {
    setSelectedIds(new Set(availableActions.map((a) => a.id)));
  };

  const handleClearAll = () => {
    setSelectedIds(new Set());
  };

  const handleExecute = () => {
    if (selectedIds.size === 0) return;
    onExecute(Array.from(selectedIds));
    setSelectedIds(new Set());
    setIsOpen(false);
  };

  return (
    <div className="action-multi-selector">
      <button
        className="btn btn-secondary"
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled || availableActions.length === 0}
      >
        Run Actions {selectedIds.size > 0 && `(${selectedIds.size})`}
      </button>

      {isOpen && (
        <div className="action-dropdown">
          <div className="action-dropdown-header">
            <span>Select Actions</span>
            <div className="action-dropdown-controls">
              <button className="link-button" onClick={handleSelectAll}>
                All
              </button>
              <button className="link-button" onClick={handleClearAll}>
                Clear
              </button>
            </div>
          </div>

          <div className="action-dropdown-body">
            {categories.length === 0 && (
              <div className="empty-state">No actions available</div>
            )}

            {categories.map((category) => (
              <div key={category} className="action-category">
                <div className="action-category-label">
                  {category.charAt(0).toUpperCase() + category.slice(1)}
                </div>
                {groupedActions[category].map((action) => (
                  <label key={action.id} className="action-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(action.id)}
                      onChange={() => handleToggle(action.id)}
                    />
                    <span className="action-checkbox-label">
                      {action.label}
                      <span className={`badge badge-risk-${action.riskLevel}`}>
                        Risk {action.riskLevel}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            ))}
          </div>

          <div className="action-dropdown-footer">
            <button className="btn btn-secondary" onClick={() => setIsOpen(false)}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleExecute}
              disabled={selectedIds.size === 0}
            >
              Execute {selectedIds.size > 0 && `${selectedIds.size} action${selectedIds.size !== 1 ? "s" : ""}`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
