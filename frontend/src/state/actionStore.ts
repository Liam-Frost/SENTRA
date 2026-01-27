import { useSyncExternalStore } from "react";

import {
  createAction as createActionApi,
  deleteAction as deleteActionApi,
  listActions,
  updateAction as updateActionApi,
  type Action,
} from "../api/actions";

type StoreState = {
  actions: Action[];
  loading: boolean;
};

let store: StoreState = {
  actions: [],
  loading: false,
};

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function setStore(next: StoreState) {
  store = next;
  emit();
}

export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSnapshot() {
  return store;
}

export function useActionStore() {
  return useSyncExternalStore(subscribe, getSnapshot);
}

export async function refreshActionsFromBackend() {
  if (typeof window === "undefined") return;
  
  setStore({ ...store, loading: true });
  
  try {
    const data = await listActions();
    if (!data || !Array.isArray(data.actions)) {
      setStore({ ...store, loading: false });
      return;
    }
    
    setStore({ actions: data.actions, loading: false });
  } catch (error) {
    console.error("Failed to load actions:", error);
    setStore({ ...store, loading: false });
  }
}

export function getAction(id: string): Action | null {
  return store.actions.find((a) => a.id === id) ?? null;
}

export function getAvailableActions(
  capability?: "simulation" | "probe" | "both"
): Action[] {
  return store.actions.filter((action) => {
    if (action.availability !== "available") return false;
    if (!capability) return true;
    
    // Match capability
    if (action.capability === "both") return true;
    if (capability === "both") return true;
    return action.capability === capability;
  });
}

export function getActionsByCategory(category: string): Action[] {
  return store.actions.filter((a) => a.category === category);
}

export function getSystemActions(): Action[] {
  return store.actions.filter((a) => a.isSystem);
}

export function getCustomActions(): Action[] {
  return store.actions.filter((a) => !a.isSystem);
}

export async function createAction(data: Partial<Action>): Promise<Action> {
  try {
    const result = await createActionApi(data);
    
    // Refresh from backend to get the complete action
    await refreshActionsFromBackend();
    
    return result.action;
  } catch (error) {
    console.error("Failed to create action:", error);
    throw error;
  }
}

export async function updateAction(
  id: string,
  data: Partial<Action>
): Promise<Action> {
  try {
    const result = await updateActionApi(id, data);
    
    // Update local store
    const updatedActions = store.actions.map((action) =>
      action.id === id ? result.action : action
    );
    setStore({ ...store, actions: updatedActions });
    
    return result.action;
  } catch (error) {
    console.error("Failed to update action:", error);
    throw error;
  }
}

export async function deleteAction(id: string): Promise<void> {
  try {
    await deleteActionApi(id);
    
    // Remove from local store
    const filteredActions = store.actions.filter((action) => action.id !== id);
    setStore({ ...store, actions: filteredActions });
  } catch (error) {
    console.error("Failed to delete action:", error);
    throw error;
  }
}

export async function duplicateAction(id: string): Promise<Action | null> {
  const existing = getAction(id);
  if (!existing) return null;
  
  // Generate new ID by appending timestamp
  const newId = `${existing.id}_copy_${Date.now()}`;
  
  const duplicated = await createAction({
    id: newId,
    label: `${existing.label} (copy)`,
    category: existing.category,
    capability: existing.capability,
    availability: existing.availability,
    riskLevel: existing.riskLevel,
    requiresTarget: existing.requiresTarget,
    description: existing.description,
    parametersSchema: existing.parametersSchema,
    defaultParameters: existing.defaultParameters,
  });
  
  return duplicated;
}

// Auto-load actions on module init
if (typeof window !== "undefined") {
  void refreshActionsFromBackend();
}
