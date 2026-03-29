from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Sequence

from app.persistence import db
from app.services import operation_service


def list_templates(conn: Any) -> Dict[str, List[Dict[str, Any]]]:
    rows = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM operation_templates ORDER BY updated_at DESC, name ASC"
    )
    templates = [_hydrate_template(row, conn) for row in rows]
    return {"templates": templates}


def get_template(template_id: str, conn: Any) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM operation_templates WHERE id = ?",
        (template_id,),
    ).fetchone()
    if not row:
        return None
    return _hydrate_template(row, conn)


def create_template(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    normalized = _normalize_template_input(payload)
    now_ms = _now_ms()
    template_id = str(normalized.get("id") or operation_service._next_id("tpl"))
    conn.execute(
        "INSERT INTO operation_templates (id, name, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (template_id, normalized["name"], normalized.get("description"), now_ms, now_ms),
    )
    _replace_steps(template_id, normalized["steps"], conn)
    conn.commit()
    return get_template(template_id, conn) or {
        "id": template_id,
        "name": normalized["name"],
        "description": normalized.get("description"),
        "steps": normalized["steps"],
        "createdAt": now_ms,
        "updatedAt": now_ms,
    }


def update_template(template_id: str, payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    existing = get_template(template_id, conn)
    if not existing:
        raise ValueError("template not found")

    merged = {
        "id": template_id,
        "name": payload.get("name", existing["name"]),
        "description": payload.get("description", existing.get("description")),
        "steps": payload.get("steps", existing.get("steps", [])),
    }
    normalized = _normalize_template_input(merged)
    now_ms = _now_ms()
    conn.execute(
        "UPDATE operation_templates SET name = ?, description = ?, updated_at = ? WHERE id = ?",
        (normalized["name"], normalized.get("description"), now_ms, template_id),
    )
    _replace_steps(template_id, normalized["steps"], conn)
    conn.commit()
    return get_template(template_id, conn) or existing


def delete_template(template_id: str, conn: Any) -> bool:
    conn.execute("DELETE FROM operation_template_steps WHERE template_id = ?", (template_id,))
    cursor = conn.execute("DELETE FROM operation_templates WHERE id = ?", (template_id,))
    conn.commit()
    return cursor.rowcount > 0


def list_executions(
    conn: Any,
    *,
    template_id: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, List[Dict[str, Any]]]:
    rows = conn.execute(
        "SELECT * FROM operations WHERE action_type = ? ORDER BY created_at DESC LIMIT ?",
        ("template_execution", int(limit)),
    )
    executions: List[Dict[str, Any]] = []
    for row in rows:
        item = _row_to_execution(row)
        params = item.get("parameters") if isinstance(item.get("parameters"), dict) else {}
        if template_id and str(params.get("template_id") or "") != template_id:
            continue
        if source and str(params.get("source") or "") != source:
            continue
        executions.append(item)
    return {"executions": executions}


def get_execution(execution_id: str, conn: Any) -> Optional[Dict[str, Any]]:
    result = operation_service.get_operation(execution_id, conn=conn)
    if not result:
        return None
    operation = result.get("operation") if isinstance(result, dict) else None
    if not isinstance(operation, dict) or operation.get("actionType") != "template_execution":
        return None
    logs = operation_service.list_operation_logs(execution_id, conn=conn).get("logs", [])
    return {
        "execution": operation,
        "runs": result.get("runs", []),
        "logs": logs,
    }


def execute_template(
    template_id: str,
    targets: Sequence[str],
    *,
    initiator: str,
    conn: Any,
    source: str = "manual",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    template = get_template(template_id, conn)
    if not template:
        raise ValueError("template not found")
    return execute_template_like_payload(
        template,
        targets=targets,
        initiator=initiator,
        source=source,
        metadata=metadata,
        conn=conn,
    )


def execute_template_like_payload(
    template: Dict[str, Any],
    targets: Sequence[str],
    *,
    initiator: str,
    source: str,
    metadata: Optional[Dict[str, Any]],
    conn: Any,
) -> Dict[str, Any]:
    target_list = [str(item) for item in targets if isinstance(item, str) and item.strip()]
    if not target_list:
        raise ValueError("targets are required")

    steps = []
    for index, step in enumerate(template.get("steps", []), start=1):
        if not isinstance(step, dict):
            continue
        steps.append(
            {
                "position": int(step.get("position") or index),
                "name": str(step.get("name") or f"Step {index}"),
                "command": str(step.get("command") or ""),
                "timeoutSec": int(step.get("timeoutSec") or step.get("timeout_sec") or 60),
                "continueOnError": bool(step.get("continueOnError") or step.get("continue_on_error")),
            }
        )
    if len(steps) == 0:
        raise ValueError("template requires at least one step")

    parameters = {
        "template_id": template.get("id"),
        "template_name": template.get("name"),
        "source": source,
        "steps": steps,
    }
    if isinstance(metadata, dict):
        parameters.update(metadata)

    operation = operation_service.create_operation(
        action_type="template_execution",
        targets=target_list,
        parameters=parameters,
        initiator=initiator,
        mode="real",
        conn=conn,
    )
    return operation


def _replace_steps(template_id: str, steps: List[Dict[str, Any]], conn: Any) -> None:
    conn.execute("DELETE FROM operation_template_steps WHERE template_id = ?", (template_id,))
    for index, step in enumerate(steps, start=1):
        conn.execute(
            """
            INSERT INTO operation_template_steps (template_id, position, name, command, timeout_sec, continue_on_error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                template_id,
                int(step.get("position") or index),
                str(step["name"]),
                str(step["command"]),
                int(step.get("timeoutSec") or 60),
                1 if bool(step.get("continueOnError")) else 0,
            ),
        )


def _hydrate_template(row: Any, conn: Any) -> Dict[str, Any]:
    steps = conn.execute(
        "SELECT id, position, name, command, timeout_sec, continue_on_error FROM operation_template_steps WHERE template_id = ? ORDER BY position ASC, id ASC",
        (row["id"],),
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "description": _row_get(row, "description"),
        "steps": [
            {
                "id": item["id"],
                "position": int(item["position"]),
                "name": item["name"],
                "command": item["command"],
                "timeoutSec": int(item["timeout_sec"]),
                "continueOnError": bool(item["continue_on_error"]),
            }
            for item in steps
        ],
        "createdAt": int(row["created_at"]),
        "updatedAt": int(row["updated_at"]),
    }


def _normalize_template_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("template payload must be an object")
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    description_raw = payload.get("description")
    description = str(description_raw).strip() if isinstance(description_raw, str) else None
    steps_raw = payload.get("steps")
    if not isinstance(steps_raw, list) or len(steps_raw) == 0:
        raise ValueError("steps must be a non-empty list")

    steps: List[Dict[str, Any]] = []
    for index, raw_step in enumerate(steps_raw, start=1):
        if not isinstance(raw_step, dict):
            raise ValueError("each step must be an object")
        command = str(raw_step.get("command") or "").strip()
        if not command:
            raise ValueError(f"step {index} command is required")
        step_name = str(raw_step.get("name") or f"Step {index}").strip() or f"Step {index}"
        timeout_sec = raw_step.get("timeoutSec")
        if timeout_sec is None:
            timeout_sec = raw_step.get("timeout_sec")
        timeout_value = int(timeout_sec) if isinstance(timeout_sec, (int, float)) else 60
        steps.append(
            {
                "position": index,
                "name": step_name,
                "command": command,
                "timeoutSec": max(1, timeout_value),
                "continueOnError": bool(raw_step.get("continueOnError") or raw_step.get("continue_on_error")),
            }
        )

    return {
        "id": payload.get("id"),
        "name": name,
        "description": description,
        "steps": steps,
    }


def _row_to_execution(row: Any) -> Dict[str, Any]:
    parameters = _parse_json(_row_get(row, "parameters"))
    targets = _parse_json(_row_get(row, "targets"))
    return {
        "id": row["id"],
        "templateId": parameters.get("template_id"),
        "templateName": parameters.get("template_name"),
        "source": parameters.get("source") or "manual",
        "status": row["status"],
        "targets": targets if isinstance(targets, list) else [],
        "initiator": row["initiator"],
        "createdAt": int(row["created_at"]),
        "updatedAt": int(row["updated_at"]),
        "parameters": parameters,
    }


def _parse_json(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if raw is None:
        return None
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return default


def _now_ms() -> int:
    return int(time.time() * 1000)
