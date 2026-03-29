from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
import time

from app.services import operation_service, operation_templates_service


ALLOWED_STATUSES = {"draft", "active"}
ALLOWED_DR_MODES = {"manual", "active-standby", "weighted-failover"}


def list_policies(conn: Any, *, project_id: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    sql = "SELECT * FROM lb_policies"
    params: List[Any] = []
    if project_id:
        sql += " WHERE project_id = ?"
        params.append(project_id)
    sql += " ORDER BY updated_at DESC, name ASC"
    rows = conn.execute(sql, params)
    return {"policies": [_hydrate_policy(row, conn) for row in rows]}


def get_policy(policy_id: str, conn: Any) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM lb_policies WHERE id = ?", (policy_id,)).fetchone()
    if not row:
        return None
    return _hydrate_policy(row, conn)


def create_policy(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    normalized = _normalize_policy_payload(payload, conn)
    policy_id = str(normalized.get("id") or operation_service._next_id("lbp"))
    now_ms = _now_ms()
    conn.execute(
        """
        INSERT INTO lb_policies (
            id, project_id, name, description, status, dr_mode, health_check_path,
            health_check_interval_sec, failure_threshold, recovery_threshold, auto_failback,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            policy_id,
            normalized["projectId"],
            normalized["name"],
            normalized.get("description"),
            normalized["status"],
            normalized["drMode"],
            normalized.get("healthCheckPath"),
            normalized["healthCheckIntervalSec"],
            normalized["failureThreshold"],
            normalized["recoveryThreshold"],
            1 if normalized["autoFailback"] else 0,
            now_ms,
            now_ms,
        ),
    )
    _replace_allocations(policy_id, normalized["allocations"], conn)
    conn.commit()
    return get_policy(policy_id, conn) or {"id": policy_id}


def update_policy(policy_id: str, payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    existing = get_policy(policy_id, conn)
    if not existing:
        raise ValueError("policy not found")

    merged = {
        "id": policy_id,
        "projectId": payload.get("projectId", existing["projectId"]),
        "name": payload.get("name", existing["name"]),
        "description": payload.get("description", existing.get("description")),
        "status": payload.get("status", existing["status"]),
        "drMode": payload.get("drMode", existing["drMode"]),
        "healthCheckPath": payload.get("healthCheckPath", existing.get("healthCheckPath")),
        "healthCheckIntervalSec": payload.get(
            "healthCheckIntervalSec", existing["healthCheckIntervalSec"]
        ),
        "failureThreshold": payload.get("failureThreshold", existing["failureThreshold"]),
        "recoveryThreshold": payload.get("recoveryThreshold", existing["recoveryThreshold"]),
        "autoFailback": payload.get("autoFailback", existing["autoFailback"]),
        "allocations": payload.get("allocations", existing.get("allocations", [])),
    }
    normalized = _normalize_policy_payload(merged, conn)
    now_ms = _now_ms()
    conn.execute(
        """
        UPDATE lb_policies
        SET project_id = ?, name = ?, description = ?, status = ?, dr_mode = ?, health_check_path = ?,
            health_check_interval_sec = ?, failure_threshold = ?, recovery_threshold = ?, auto_failback = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            normalized["projectId"],
            normalized["name"],
            normalized.get("description"),
            normalized["status"],
            normalized["drMode"],
            normalized.get("healthCheckPath"),
            normalized["healthCheckIntervalSec"],
            normalized["failureThreshold"],
            normalized["recoveryThreshold"],
            1 if normalized["autoFailback"] else 0,
            now_ms,
            policy_id,
        ),
    )
    _replace_allocations(policy_id, normalized["allocations"], conn)
    conn.commit()
    return get_policy(policy_id, conn) or existing


def delete_policy(policy_id: str, conn: Any) -> bool:
    conn.execute("DELETE FROM lb_policy_allocations WHERE policy_id = ?", (policy_id,))
    cursor = conn.execute("DELETE FROM lb_policies WHERE id = ?", (policy_id,))
    conn.commit()
    return cursor.rowcount > 0


def apply_policy(policy_id: str, *, initiator: str, conn: Any) -> Dict[str, Any]:
    policy = get_policy(policy_id, conn)
    if not policy:
        raise ValueError("policy not found")
    enabled_allocations = [item for item in policy.get("allocations", []) if item.get("enabled")]
    targets = [str(item["nodeId"]) for item in enabled_allocations if isinstance(item.get("nodeId"), str)]
    if not targets:
        raise ValueError("policy requires at least one enabled node")

    allocation_summary = ", ".join(
        f"{item['nodeId']}={item['weight']}" for item in enabled_allocations
    )
    template = {
        "steps": [
            {
                "name": "Render policy payload",
                "command": f"echo Applying LB policy {policy['name']} for project {policy['projectId']}",
                "timeoutSec": 30,
                "continueOnError": False,
            },
            {
                "name": "Apply allocation",
                "command": f"echo Traffic allocation {allocation_summary}",
                "timeoutSec": 30,
                "continueOnError": False,
            },
            {
                "name": "Reload balancer",
                "command": f"echo Reload load balancer for project {policy['projectId']}",
                "timeoutSec": 30,
                "continueOnError": False,
            },
        ]
    }
    execution = operation_templates_service.execute_template_like_payload(
        template,
        targets=targets,
        initiator=initiator,
        source="lb_policy_apply",
        metadata={"lb_policy_id": policy_id, "project_id": policy["projectId"], "policy_name": policy["name"]},
        conn=conn,
    )
    return {"policy": policy, "execution": execution}


def _replace_allocations(policy_id: str, allocations: Sequence[Dict[str, Any]], conn: Any) -> None:
    conn.execute("DELETE FROM lb_policy_allocations WHERE policy_id = ?", (policy_id,))
    for item in allocations:
        conn.execute(
            "INSERT INTO lb_policy_allocations (policy_id, node_id, weight, enabled, priority) VALUES (?, ?, ?, ?, ?)",
            (
                policy_id,
                str(item["nodeId"]),
                int(item["weight"]),
                1 if bool(item.get("enabled")) else 0,
                int(item.get("priority") or 100),
            ),
        )


def _hydrate_policy(row: Any, conn: Any) -> Dict[str, Any]:
    allocations = conn.execute(
        "SELECT id, node_id, weight, enabled, priority FROM lb_policy_allocations WHERE policy_id = ? ORDER BY priority ASC, node_id ASC",
        (row["id"],),
    )
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "name": row["name"],
        "description": _row_get(row, "description"),
        "status": row["status"],
        "drMode": row["dr_mode"],
        "healthCheckPath": _row_get(row, "health_check_path"),
        "healthCheckIntervalSec": int(row["health_check_interval_sec"]),
        "failureThreshold": int(row["failure_threshold"]),
        "recoveryThreshold": int(row["recovery_threshold"]),
        "autoFailback": bool(row["auto_failback"]),
        "allocations": [
            {
                "id": item["id"],
                "nodeId": item["node_id"],
                "weight": int(item["weight"]),
                "enabled": bool(item["enabled"]),
                "priority": int(item["priority"]),
            }
            for item in allocations
        ],
        "createdAt": int(row["created_at"]),
        "updatedAt": int(row["updated_at"]),
    }


def _normalize_policy_payload(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("policy payload must be an object")
    project_id = str(payload.get("projectId") or payload.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("projectId is required")
    project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise ValueError("project not found")

    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    status = str(payload.get("status") or "draft").strip().lower()
    if status not in ALLOWED_STATUSES:
        raise ValueError("status must be draft or active")
    dr_mode = str(payload.get("drMode") or payload.get("dr_mode") or "manual").strip().lower()
    if dr_mode not in ALLOWED_DR_MODES:
        raise ValueError("drMode must be manual, active-standby, or weighted-failover")

    allocations_raw = payload.get("allocations")
    allocations: List[Dict[str, Any]] = []
    if allocations_raw is not None:
        if not isinstance(allocations_raw, list):
            raise ValueError("allocations must be a list")
        for index, raw in enumerate(allocations_raw, start=1):
            if not isinstance(raw, dict):
                raise ValueError("each allocation must be an object")
            node_id = str(raw.get("nodeId") or raw.get("node_id") or "").strip()
            if not node_id:
                raise ValueError(f"allocation {index} requires nodeId")
            node = conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,)).fetchone()
            if not node:
                raise ValueError(f"allocation node not found: {node_id}")
            weight = int(raw.get("weight") or 0)
            priority = int(raw.get("priority") or index)
            allocations.append(
                {
                    "nodeId": node_id,
                    "weight": max(0, min(100, weight)),
                    "enabled": bool(raw.get("enabled", True)),
                    "priority": priority,
                }
            )

    enabled = [item for item in allocations if item.get("enabled")]
    if enabled:
        total = sum(int(item["weight"]) for item in enabled)
        if total != 100:
            raise ValueError("enabled node weights must sum to 100")

    description = payload.get("description")
    description_value = str(description).strip() if isinstance(description, str) else None
    health_path = payload.get("healthCheckPath") or payload.get("health_check_path")
    health_path_value = str(health_path).strip() if isinstance(health_path, str) else "/healthz"

    interval = int(payload.get("healthCheckIntervalSec") or payload.get("health_check_interval_sec") or 10)
    failure_threshold = int(payload.get("failureThreshold") or payload.get("failure_threshold") or 3)
    recovery_threshold = int(payload.get("recoveryThreshold") or payload.get("recovery_threshold") or 2)

    return {
        "id": payload.get("id"),
        "projectId": project_id,
        "name": name,
        "description": description_value,
        "status": status,
        "drMode": dr_mode,
        "healthCheckPath": health_path_value,
        "healthCheckIntervalSec": max(1, interval),
        "failureThreshold": max(1, failure_threshold),
        "recoveryThreshold": max(1, recovery_threshold),
        "autoFailback": bool(payload.get("autoFailback") or payload.get("auto_failback")),
        "allocations": allocations,
    }


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
