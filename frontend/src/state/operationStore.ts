import { useSyncExternalStore } from "react";

import type { Operation, OperationRun } from "../api/operations";
import {
  createOperation as createOperationApi,
  deleteOperation as deleteOperationApi,
  getOperation,
  listOperations
} from "../api/operations";

type StoreState = {
  operations: Operation[];
  runs: OperationRun[];
  loading: boolean;
  error: string | null;
};

let store: StoreState = {
  operations: [],
  runs: [],
  loading: false,
  error: null
};

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function setStore(next: Partial<StoreState>) {
  store = { ...store, ...next };
  emit();
}

export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getSnapshot() {
  return store;
}

export function useOperationStore() {
  return useSyncExternalStore(subscribe, getSnapshot);
}

export async function refreshOperations() {
  setStore({ loading: true });
  try {
    const data = await listOperations();
    const operations = Array.isArray(data.operations) ? data.operations : [];
    setStore({ operations, loading: false, error: null });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to load operations";
    setStore({ loading: false, error: message });
  }
}

export async function refreshOperation(operationId: string) {
  try {
    const data = await getOperation(operationId);
    const nextOperations = store.operations.map((op) =>
      op.id === data.operation.id ? data.operation : op
    );
    const nextRuns = [
      ...store.runs.filter((run) => run.operationId !== data.operation.id),
      ...data.runs
    ];
    setStore({ operations: nextOperations, runs: nextRuns, error: null });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to load operation";
    setStore({ error: message });
  }
}

export async function createOperation(input: {
  action: string;
  targets: string[];
  parameters?: Record<string, unknown>;
  initiator?: string;
  approval_state?: "none" | "pending" | "approved" | "rejected";
}) {
  const created = await createOperationApi(input);
  if (created?.operation) {
    setStore({ operations: [created.operation, ...store.operations] });
    return created.operation;
  }
  return null;
}

export async function deleteOperation(operationId: string) {
  await deleteOperationApi(operationId);
  setStore({
    operations: store.operations.filter((op) => op.id !== operationId),
    runs: store.runs.filter((run) => run.operationId !== operationId)
  });
}
