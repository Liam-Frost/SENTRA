from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Sequence

from app.core import actions as action_catalog
from app.persistence import db


ALLOWED_STATUSES = {"queued", "running", "succeeded", "failed", "partial", "cancelled"}
ALLOWED_APPROVAL = {"none", "pending", "approved", "rejected"}
ALLOWED_MODES = {"simulation", "real"}
FINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled"}

_OP_ID_LOCK = threading.RLock()
_OP_COUNTER = 0


def get_run_mode() -> str:
    raw = os.getenv("SENTRA_RUN_MODE", "real")
    mode = str(raw or "real").lower()
    if mode not in ALLOWED_MODES:
        return "real"
    return mode


def list_operations(
    status: Optional[str] = None,
    limit: Optional[int] = None,
    conn: Optional[Any] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    sql = "SELECT * FROM operations"
    params: List[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))

    cursor = conn.execute(sql, params)
    operations = [_row_to_operation(row) for row in cursor]

    if close_conn:
        conn.close()
    return {"operations": operations}


def list_pending_operations(conn: Any) -> List[Dict[str, Any]]:
    cursor = conn.execute(
        """
        SELECT *
        FROM operations
        WHERE status IN ('queued', 'running')
        ORDER BY created_at ASC
        """
    )
    return [_row_to_operation(row) for row in cursor]


def get_operation(operation_id: str, conn: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    row = conn.execute("SELECT * FROM operations WHERE id = ?", (operation_id,)).fetchone()
    if not row:
        if close_conn:
            conn.close()
        return None
    operation = _row_to_operation(row)
    runs = list_operation_runs(operation_id, conn=conn)

    if close_conn:
        conn.close()
    return {"operation": operation, "runs": runs}


def list_operation_runs(operation_id: str, conn: Optional[Any] = None) -> List[Dict[str, Any]]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    cursor = conn.execute(
        "SELECT * FROM operation_runs WHERE operation_id = ? ORDER BY id ASC",
        (operation_id,),
    )
    runs = [_row_to_run(row) for row in cursor]

    if close_conn:
        conn.close()
    return runs


def create_operation(
    *,
    action_type: str,
    targets: Sequence[str],
    parameters: Optional[Dict[str, Any]] = None,
    initiator: str = "manual",
    approval_state: str = "none",
    mode: Optional[str] = None,
    policy_id: Optional[str] = None,
    policy_version: Optional[int] = None,
    policy_name: Optional[str] = None,
    conn: Optional[Any] = None,
) -> Dict[str, Any]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)
    
    spec = action_catalog.get_action(action_type, conn)
    if spec is None:
        if close_conn:
            conn.close()
        raise ValueError("invalid action type")

    target_list = [str(t) for t in targets if isinstance(t, str) and t.strip()]
    if spec.requires_target and len(target_list) == 0:
        if close_conn:
            conn.close()
        raise ValueError("targets required for action")

    if not spec.requires_target and len(target_list) == 0:
        target_list = ["fleet"]

    approval = approval_state if approval_state in ALLOWED_APPROVAL else "none"
    mode_value = mode if mode in ALLOWED_MODES else get_run_mode()

    now_ms = int(time.time() * 1000)
    op_id = _next_id("op")

    op_row = {
        "id": op_id,
        "actionType": action_type,
        "status": "queued",
        "approvalState": approval,
        "mode": mode_value,
        "targets": target_list,
        "parameters": parameters or None,
        "initiator": initiator,
        "policyId": policy_id,
        "policyVersion": policy_version,
        "policyName": policy_name,
        "createdAt": now_ms,
        "updatedAt": now_ms,
    }

    conn.execute(
        """
        INSERT INTO operations (
            id, action_type, status, approval_state, mode, targets, parameters,
            initiator, policy_id, policy_version, policy_name, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            op_row["id"],
            op_row["actionType"],
            op_row["status"],
            op_row["approvalState"],
            op_row["mode"],
            json.dumps(op_row["targets"], ensure_ascii=True),
            json.dumps(op_row["parameters"], ensure_ascii=True)
            if op_row["parameters"] is not None
            else None,
            op_row["initiator"],
            op_row["policyId"],
            op_row["policyVersion"],
            op_row["policyName"],
            op_row["createdAt"],
            op_row["updatedAt"],
        ),
    )

    for target in op_row["targets"]:
        conn.execute(
            """
            INSERT INTO operation_runs (operation_id, node_id, status)
            VALUES (?, ?, ?)
            """,
            (op_id, target, "queued"),
        )

    conn.commit()

    if close_conn:
        conn.close()

    return op_row


def update_operation_status(
    operation_id: str,
    status: str,
    conn: Any,
) -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError("invalid status")
    now_ms = int(time.time() * 1000)
    conn.execute(
        "UPDATE operations SET status = ?, updated_at = ? WHERE id = ?",
        (status, now_ms, operation_id),
    )


def update_operation_approval(operation_id: str, approval_state: str, conn: Any) -> None:
    if approval_state not in ALLOWED_APPROVAL:
        raise ValueError("invalid approval state")
    now_ms = int(time.time() * 1000)
    conn.execute(
        "UPDATE operations SET approval_state = ?, updated_at = ? WHERE id = ?",
        (approval_state, now_ms, operation_id),
    )


def update_run_status(
    run_id: int,
    status: str,
    conn: Any,
    started_at: Optional[int] = None,
    finished_at: Optional[int] = None,
    output: Optional[str] = None,
    exit_code: Optional[int] = None,
) -> None:
    updates: List[str] = ["status = ?"]
    params: List[Any] = [status]
    if started_at is not None:
        updates.append("started_at = ?")
        params.append(started_at)
    if finished_at is not None:
        updates.append("finished_at = ?")
        params.append(finished_at)
    if output is not None:
        updates.append("output = ?")
        params.append(output)
    if exit_code is not None:
        updates.append("exit_code = ?")
        params.append(exit_code)
    params.append(run_id)
    conn.execute(f"UPDATE operation_runs SET {', '.join(updates)} WHERE id = ?", params)


def claim_next_run_for_node(node_id: str, conn: Any) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        """
        SELECT
            r.id,
            r.operation_id,
            r.node_id,
            r.status,
            o.action_type,
            o.parameters,
            o.mode,
            o.status AS operation_status,
            o.approval_state
        FROM operation_runs r
        JOIN operations o ON o.id = r.operation_id
        WHERE r.node_id = ?
          AND r.status = 'queued'
          AND o.status IN ('queued', 'running')
          AND o.approval_state IN ('none', 'approved')
        ORDER BY r.id ASC
        LIMIT 1
        """,
        (node_id,),
    ).fetchone()
    if not row:
        return None

    run_id = int(row["id"])
    now_ms = int(time.time() * 1000)
    update_run_status(run_id, "running", conn, started_at=now_ms)
    if str(_row_get(row, "operation_status") or "") == "queued":
        update_operation_status(str(row["operation_id"]), "running", conn)

    params_raw = _row_get(row, "parameters")
    parameters: Optional[Dict[str, Any]] = None
    if params_raw:
        try:
            decoded = json.loads(params_raw)
            parameters = decoded if isinstance(decoded, dict) else None
        except json.JSONDecodeError:
            parameters = None

    conn.commit()
    return {
        "runId": run_id,
        "operationId": row["operation_id"],
        "nodeId": _row_get(row, "node_id"),
        "action": row["action_type"],
        "parameters": parameters,
        "mode": _row_get(row, "mode"),
    }


def append_run_log(
    run_id: int,
    stream: str,
    message: str,
    conn: Any,
    ts: Optional[int] = None,
) -> Dict[str, Any]:
    if stream not in {"stdout", "stderr", "system"}:
        stream = "system"
    timestamp = int(ts) if isinstance(ts, int) else int(time.time() * 1000)

    run = conn.execute(
        "SELECT id, operation_id, node_id FROM operation_runs WHERE id = ?",
        (int(run_id),),
    ).fetchone()
    if not run:
        raise ValueError("run not found")

    if db.is_postgres(conn):
        cursor = conn.execute(
            """
            INSERT INTO operation_run_logs (run_id, operation_id, node_id, stream, message, ts)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                int(run_id),
                str(run["operation_id"]),
                _row_get(run, "node_id"),
                stream,
                str(message),
                timestamp,
            ),
        )
        inserted = cursor.fetchone() or {}
        log_id = int(inserted.get("id", 0)) if isinstance(inserted, dict) else int(inserted[0])
    else:
        cursor = conn.execute(
            """
            INSERT INTO operation_run_logs (run_id, operation_id, node_id, stream, message, ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(run_id),
                str(run["operation_id"]),
                _row_get(run, "node_id"),
                stream,
                str(message),
                timestamp,
            ),
        )
        log_id = int(cursor.lastrowid or 0)
    conn.commit()
    return {
        "id": log_id,
        "runId": int(run_id),
        "operationId": str(run["operation_id"]),
        "nodeId": _row_get(run, "node_id"),
        "stream": stream,
        "message": str(message),
        "ts": timestamp,
    }


def list_operation_logs(operation_id: str, conn: Any) -> Dict[str, List[Dict[str, Any]]]:
    cursor = conn.execute(
        """
        SELECT id, run_id, operation_id, node_id, stream, message, ts
        FROM operation_run_logs
        WHERE operation_id = ?
        ORDER BY id ASC
        """,
        (operation_id,),
    )
    logs = [
        {
            "id": row["id"],
            "runId": row["run_id"],
            "operationId": row["operation_id"],
            "nodeId": row["node_id"],
            "stream": row["stream"],
            "message": row["message"],
            "ts": row["ts"],
        }
        for row in cursor
    ]
    return {"logs": logs}


def complete_run(
    run_id: int,
    *,
    status: str,
    output: Optional[str],
    exit_code: Optional[int],
    conn: Any,
    finished_at: Optional[int] = None,
) -> Dict[str, Any]:
    status_value = str(status or "").lower()
    if status_value not in FINAL_RUN_STATUSES:
        raise ValueError("status must be succeeded, failed, or cancelled")

    row = conn.execute(
        "SELECT id, operation_id, node_id FROM operation_runs WHERE id = ?",
        (int(run_id),),
    ).fetchone()
    if not row:
        raise ValueError("run not found")

    ts = int(finished_at) if isinstance(finished_at, int) else int(time.time() * 1000)
    code = int(exit_code) if isinstance(exit_code, int) else (0 if status_value == "succeeded" else 1)
    update_run_status(
        int(run_id),
        status_value,
        conn,
        finished_at=ts,
        output=output,
        exit_code=code,
    )
    operation_status = recalculate_operation_status(str(row["operation_id"]), conn=conn)
    conn.commit()
    return {
        "runId": int(run_id),
        "operationId": str(row["operation_id"]),
        "nodeId": _row_get(row, "node_id"),
        "status": status_value,
        "operationStatus": operation_status,
    }


def recalculate_operation_status(operation_id: str, conn: Any) -> str:
    runs = list_operation_runs(operation_id, conn=conn)
    statuses = [str(run.get("status") or "") for run in runs]
    if not statuses:
        update_operation_status(operation_id, "failed", conn)
        return "failed"

    if all(status == "cancelled" for status in statuses):
        update_operation_status(operation_id, "cancelled", conn)
        return "cancelled"

    if any(status in {"queued", "running"} for status in statuses):
        update_operation_status(operation_id, "running", conn)
        return "running"

    succeeded = statuses.count("succeeded")
    failed = statuses.count("failed")
    cancelled = statuses.count("cancelled")

    if failed == 0 and cancelled == 0 and succeeded == len(statuses):
        update_operation_status(operation_id, "succeeded", conn)
        return "succeeded"
    if succeeded == 0 and cancelled == 0 and failed == len(statuses):
        update_operation_status(operation_id, "failed", conn)
        return "failed"
    if succeeded == 0 and failed == 0 and cancelled == len(statuses):
        update_operation_status(operation_id, "cancelled", conn)
        return "cancelled"

    update_operation_status(operation_id, "partial", conn)
    return "partial"


def cancel_operation(operation_id: str, conn: Any) -> bool:
    operation = conn.execute("SELECT id FROM operations WHERE id = ?", (operation_id,)).fetchone()
    if not operation:
        return False

    now_ms = int(time.time() * 1000)
    conn.execute(
        """
        UPDATE operation_runs
        SET status = 'cancelled', finished_at = ?, output = COALESCE(output, 'cancelled'), exit_code = COALESCE(exit_code, 130)
        WHERE operation_id = ? AND status IN ('queued', 'running')
        """,
        (now_ms, operation_id),
    )
    update_operation_status(operation_id, "cancelled", conn)
    conn.commit()
    return True


def retry_operation(operation_id: str, initiator: str, conn: Any) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM operations WHERE id = ?", (operation_id,)).fetchone()
    if not row:
        raise ValueError("operation not found")

    base = _row_to_operation(row)
    runs = list_operation_runs(operation_id, conn=conn)
    retry_targets = [
        str(run.get("nodeId"))
        for run in runs
        if str(run.get("status") or "") in {"failed", "cancelled"} and run.get("nodeId")
    ]
    if not retry_targets:
        raise ValueError("no failed or cancelled runs to retry")

    return create_operation(
        action_type=str(base.get("actionType") or ""),
        targets=retry_targets,
        parameters=base.get("parameters") if isinstance(base.get("parameters"), dict) else None,
        initiator=initiator,
        approval_state="none",
        mode=str(base.get("mode") or get_run_mode()),
        conn=conn,
    )


def delete_operation(operation_id: str, conn: Optional[Any] = None) -> bool:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    conn.execute("DELETE FROM operation_runs WHERE operation_id = ?", (operation_id,))
    cursor = conn.execute("DELETE FROM operations WHERE id = ?", (operation_id,))
    conn.commit()

    if close_conn:
        conn.close()
    return cursor.rowcount > 0


def _row_to_operation(row: Any) -> Dict[str, Any]:
    targets: List[str] = []
    if row["targets"]:
        try:
            targets = json.loads(row["targets"]) or []
        except json.JSONDecodeError:
            targets = []
    parameters = None
    if row["parameters"]:
        try:
            parameters = json.loads(row["parameters"])
        except json.JSONDecodeError:
            parameters = None

    return {
        "id": row["id"],
        "actionType": row["action_type"],
        "status": row["status"],
        "approvalState": row["approval_state"],
        "mode": row["mode"],
        "targets": targets,
        "parameters": parameters,
        "initiator": row["initiator"],
        "policyId": row["policy_id"],
        "policyVersion": row["policy_version"],
        "policyName": row["policy_name"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _row_to_run(row: Any) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "operationId": row["operation_id"],
        "nodeId": row["node_id"],
        "status": row["status"],
        "startedAt": row["started_at"],
        "finishedAt": row["finished_at"],
        "output": row["output"],
        "exitCode": row["exit_code"],
    }


def _next_id(prefix: str) -> str:
    global _OP_COUNTER
    with _OP_ID_LOCK:
        _OP_COUNTER += 1
        return f"{prefix}-{int(time.time() * 1000)}-{_OP_COUNTER}"


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return default
