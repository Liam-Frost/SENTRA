from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.core import actions as action_catalog
from app.services import event_service, operation_service


def process_pending(
    world_state: Dict[str, Any],
    execute_action_fn: Optional[Any],
    conn: Any,
) -> Dict[str, Any]:
    if not isinstance(world_state, dict):
        return world_state

    run_mode = operation_service.get_run_mode()
    operations = operation_service.list_pending_operations(conn=conn)
    for operation in operations:
        status = operation.get("status")
        approval_state = operation.get("approvalState")
        if status not in {"queued", "running"}:
            continue
        if approval_state in {"pending", "rejected"}:
            continue

        op_id = operation.get("id")
        if not isinstance(op_id, str):
            continue
        action_type = operation.get("actionType")
        spec = action_catalog.get_action(str(action_type), conn)
        runs = operation_service.list_operation_runs(op_id, conn=conn)
        if not runs:
            continue

        operation_service.update_operation_status(op_id, "running", conn)
        now_ms = int(time.time() * 1000)

        if spec is None:
            _fail_runs(conn, runs, now_ms, "invalid_action", op_id, str(action_type))
            operation_service.update_operation_status(op_id, "failed", conn)
            continue

        if spec.availability != "available":
            _fail_runs(conn, runs, now_ms, "action_unavailable", op_id, spec.type)
            operation_service.update_operation_status(op_id, "failed", conn)
            continue

        if run_mode == "simulation" and spec.capability == "probe":
            _noop_runs(conn, runs, now_ms, "probe_only_simulation")
            operation_service.update_operation_status(op_id, "succeeded", conn)
            continue

        if not spec.requires_target:
            allowed, reason, _blocking, noop = action_catalog.evaluate_action(
                spec.type, world_state, None, conn
            )
            if not allowed:
                _fail_runs(conn, runs, now_ms, reason, op_id, spec.type)
                operation_service.update_operation_status(op_id, "failed", conn)
                continue
            if noop:
                _noop_runs(conn, runs, now_ms, reason)
                operation_service.update_operation_status(op_id, "succeeded", conn)
                continue
            world_state = _execute_action(world_state, spec.type, None, execute_action_fn)
            _emit_action_event(world_state, spec.type, None, op_id, conn)
            _succeed_runs(conn, runs, now_ms, "executed")
            operation_service.update_operation_status(op_id, "succeeded", conn)
            continue

        run_statuses: List[str] = []
        for run in runs:
            if run.get("status") not in {"queued", "running"}:
                run_statuses.append(str(run.get("status")))
                continue
            target = run.get("nodeId")
            run_id_raw = run.get("id")
            if run_id_raw is None:
                continue
            run_id = int(run_id_raw)
            operation_service.update_run_status(run_id, "running", conn, started_at=now_ms)

            allowed, reason, _blocking, noop = action_catalog.evaluate_action(
                spec.type, world_state, target, conn
            )
            if not allowed:
                operation_service.update_run_status(
                    run_id,
                    "failed",
                    conn,
                    finished_at=now_ms,
                    output=reason,
                    exit_code=1,
                )
                _emit_blocked_event(world_state, spec.type, target, reason, op_id, conn)
                run_statuses.append("failed")
                continue
            if noop:
                operation_service.update_run_status(
                    run_id,
                    "succeeded",
                    conn,
                    finished_at=now_ms,
                    output=reason,
                    exit_code=0,
                )
                run_statuses.append("succeeded")
                continue

            world_state = _execute_action(world_state, spec.type, target, execute_action_fn)
            _emit_action_event(world_state, spec.type, target, op_id, conn)
            operation_service.update_run_status(
                run_id,
                "succeeded",
                conn,
                finished_at=now_ms,
                output="executed",
                exit_code=0,
            )
            run_statuses.append("succeeded")

        final_status = _aggregate_status(run_statuses)
        operation_service.update_operation_status(op_id, final_status, conn)

    return world_state


def _execute_action(
    world_state: Dict[str, Any],
    action: str,
    target: Optional[str],
    execute_action_fn: Optional[Any],
) -> Dict[str, Any]:
    if execute_action_fn is None:
        return world_state
    result = execute_action_fn(world_state, action, target)
    return result if isinstance(result, dict) else world_state


def _aggregate_status(statuses: List[str]) -> str:
    if not statuses:
        return "failed"
    failed = statuses.count("failed")
    succeeded = statuses.count("succeeded")
    if failed == 0 and succeeded == len(statuses):
        return "succeeded"
    if succeeded == 0 and failed == len(statuses):
        return "failed"
    return "partial"


def _fail_runs(
    conn: Any,
    runs: List[Dict[str, Any]],
    now_ms: int,
    reason: str,
    op_id: str,
    action_type: str,
) -> None:
    for run in runs:
        run_id_raw = run.get("id")
        if run_id_raw is None:
            continue
        run_id = int(run_id_raw)
        operation_service.update_run_status(
            run_id,
            "failed",
            conn,
            started_at=now_ms,
            finished_at=now_ms,
            output=reason,
            exit_code=1,
        )
    _emit_blocked_event({}, action_type, None, reason, op_id, conn)


def _noop_runs(conn: Any, runs: List[Dict[str, Any]], now_ms: int, reason: str) -> None:
    for run in runs:
        run_id_raw = run.get("id")
        if run_id_raw is None:
            continue
        run_id = int(run_id_raw)
        operation_service.update_run_status(
            run_id,
            "succeeded",
            conn,
            started_at=now_ms,
            finished_at=now_ms,
            output=reason,
            exit_code=0,
        )


def _succeed_runs(conn: Any, runs: List[Dict[str, Any]], now_ms: int, message: str) -> None:
    for run in runs:
        run_id_raw = run.get("id")
        if run_id_raw is None:
            continue
        run_id = int(run_id_raw)
        operation_service.update_run_status(
            run_id,
            "succeeded",
            conn,
            started_at=now_ms,
            finished_at=now_ms,
            output=message,
            exit_code=0,
        )


def _emit_action_event(
    world_state: Dict[str, Any],
    action: str,
    target: Optional[str],
    op_id: str,
    conn: Any,
) -> None:
    tick = int((world_state or {}).get("tick") or 0)
    payload: Dict[str, Any] = {"action": action, "operation_id": op_id}
    if target:
        payload["target"] = target
    event_service.append_event(
        tick=tick,
        event_type="action",
        message=f"execute {action} on {target or 'fleet'}",
        payload=payload,
        conn=conn,
    )


def _emit_blocked_event(
    world_state: Dict[str, Any],
    action: str,
    target: Optional[str],
    reason: str,
    op_id: str,
    conn: Any,
) -> None:
    tick = int((world_state or {}).get("tick") or 0)
    payload: Dict[str, Any] = {
        "action": action,
        "operation_id": op_id,
        "blocked": True,
        "reason": reason,
    }
    if target:
        payload["target"] = target
    event_service.append_event(
        tick=tick,
        event_type="action",
        message=f"blocked {action} on {target or 'fleet'}: {reason}",
        payload=payload,
        conn=conn,
    )
