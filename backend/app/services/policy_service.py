from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, List, Optional

from app.core import actions as action_catalog
from app.persistence import db

ALLOWED_POLICY_MODES = {"ADVISE_ONLY", "AUTO_EXECUTE"}
ALLOWED_POLICY_STATUSES = {"draft", "active", "archived"}
ALLOWED_SCOPE_TYPES = {"all", "nodes", "tag", "group"}
ALLOWED_CONDITION_GROUP_OPS = {"AND", "OR"}
ALLOWED_CONDITION_METRICS = {"temp", "load", "error_rate", "health"}
ALLOWED_CONDITION_OPS = {">", ">=", "<", "<="}
ALLOWED_ACTION_CAPABILITIES = {"simulation", "probe", "both"}
ALLOWED_ACTION_AVAILABILITIES = {"available", "future"}


_POLICY_ID_LOCK = threading.RLock()
_POLICY_ID_COUNTER = 0


def list_policies(conn: Optional[Any] = None) -> Dict[str, List[Dict[str, Any]]]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)
    ensure_default_policies(conn)

    cursor = conn.execute(
        "SELECT data FROM policies ORDER BY updated_at DESC, priority ASC, id ASC"
    )
    policies: List[Dict[str, Any]] = []
    for row in cursor:
        policy = _loads_json(row["data"])
        if isinstance(policy, dict):
            policies.append(policy)

    if close_conn:
        conn.close()

    return {"policies": policies}


def list_runnable_policies(conn: Optional[Any] = None) -> List[Dict[str, Any]]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)
    ensure_default_policies(conn)

    cursor = conn.execute(
        """
        SELECT data
        FROM policies
        WHERE status = ? AND enabled = 1
        ORDER BY priority ASC, updated_at DESC, id ASC
        """,
        ("active",),
    )
    policies: List[Dict[str, Any]] = []
    for row in cursor:
        policy = _loads_json(row["data"])
        if isinstance(policy, dict):
            policies.append(policy)

    if close_conn:
        conn.close()

    return policies


def get_policy(policy_id: str, conn: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    if not isinstance(policy_id, str) or not policy_id:
        return None

    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    row = conn.execute("SELECT data FROM policies WHERE id = ?", (policy_id,)).fetchone()
    policy = _loads_json(row["data"]) if row else None

    if close_conn:
        conn.close()

    return policy if isinstance(policy, dict) else None


def list_policy_versions(policy_id: str, conn: Optional[Any] = None) -> List[Dict[str, Any]]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    cursor = conn.execute(
        """
        SELECT version, created_at, data
        FROM policy_versions
        WHERE policy_id = ?
        ORDER BY version DESC
        """,
        (policy_id,),
    )
    versions: List[Dict[str, Any]] = []
    for row in cursor:
        data = _loads_json(row["data"])
        if not isinstance(data, dict):
            continue
        versions.append(
            {
                "version": int(row["version"]),
                "createdAt": int(row["created_at"]),
                "policy": data,
            }
        )

    if close_conn:
        conn.close()
    return versions


def create_policy(policy_in: Dict[str, Any], conn: Optional[Any] = None) -> Dict[str, Any]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)
    
    normalized, errors = normalize_policy_input(policy_in, existing=None, conn=conn)
    if errors:
        if close_conn:
            conn.close()
        raise ValueError(", ".join(errors))

    existing_row = conn.execute(
        "SELECT 1 FROM policies WHERE id = ?", (normalized["id"],)
    ).fetchone()
    if existing_row:
        raise ValueError("policy id already exists")

    data_json = json.dumps(normalized, ensure_ascii=True)
    conn.execute(
        """
        INSERT INTO policies (
            id, name, version, status, enabled, mode, priority, risk_level, created_at, updated_at, data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalized["id"],
            normalized["name"],
            int(normalized["version"]),
            normalized["status"],
            1 if normalized["enabled"] else 0,
            normalized["mode"],
            int(normalized["priority"]),
            int(normalized["riskLevel"]),
            int(normalized["createdAt"]),
            int(normalized["updatedAt"]),
            data_json,
        ),
    )
    conn.execute(
        "INSERT INTO policy_versions (policy_id, version, created_at, data) VALUES (?, ?, ?, ?)",
        (normalized["id"], int(normalized["version"]), int(normalized["updatedAt"]), data_json),
    )
    conn.commit()

    if close_conn:
        conn.close()

    return normalized


def update_policy(policy_id: str, policy_in: Dict[str, Any], conn: Optional[Any] = None) -> Dict[str, Any]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    existing = get_policy(policy_id, conn=conn)
    if existing is None:
        if close_conn:
            conn.close()
        raise KeyError("policy not found")

    normalized, errors = normalize_policy_input(policy_in, existing=existing, conn=conn)
    if errors:
        if close_conn:
            conn.close()
        raise ValueError(", ".join(errors))

    data_json = json.dumps(normalized, ensure_ascii=True)
    conn.execute(
        """
        UPDATE policies
        SET name = ?, version = ?, status = ?, enabled = ?, mode = ?, priority = ?, risk_level = ?, updated_at = ?, data = ?
        WHERE id = ?
        """,
        (
            normalized["name"],
            int(normalized["version"]),
            normalized["status"],
            1 if normalized["enabled"] else 0,
            normalized["mode"],
            int(normalized["priority"]),
            int(normalized["riskLevel"]),
            int(normalized["updatedAt"]),
            data_json,
            policy_id,
        ),
    )
    conn.execute(
        "INSERT INTO policy_versions (policy_id, version, created_at, data) VALUES (?, ?, ?, ?)",
        (policy_id, int(normalized["version"]), int(normalized["updatedAt"]), data_json),
    )
    conn.commit()

    if close_conn:
        conn.close()

    return normalized


def delete_policy(policy_id: str, conn: Optional[Any] = None) -> bool:
    if not isinstance(policy_id, str) or not policy_id:
        return False

    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    conn.execute("DELETE FROM policy_condition_state WHERE policy_id = ?", (policy_id,))
    conn.execute("DELETE FROM policy_runtime WHERE policy_id = ?", (policy_id,))
    conn.execute("DELETE FROM policy_versions WHERE policy_id = ?", (policy_id,))
    cursor = conn.execute("DELETE FROM policies WHERE id = ?", (policy_id,))
    conn.commit()

    if close_conn:
        conn.close()

    return cursor.rowcount > 0


def clear_runtime(conn: Optional[Any] = None) -> None:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)
    db.clear_policy_runtime(conn)
    if close_conn:
        conn.close()


def ensure_default_policies(conn: Optional[Any] = None) -> None:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    row = conn.execute("SELECT COUNT(*) AS n FROM policies").fetchone()
    count = row["n"] if row and "n" in row.keys() else 0
    if count and count > 0:
        if close_conn:
            conn.close()
        return

    for policy in _default_policies():
        try:
            create_policy(policy, conn=conn)
        except ValueError:
            continue

    if close_conn:
        conn.close()


def validate_policy(policy_in: Dict[str, Any], existing: Optional[Dict[str, Any]] = None, conn: Optional[Any] = None) -> List[str]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
        db.init_db(conn)
    
    _normalized, errors = normalize_policy_input(policy_in, existing=existing, validate_only=True, conn=conn)
    
    if close_conn:
        conn.close()
    
    return errors


def normalize_policy_input(
    policy_in: Dict[str, Any],
    existing: Optional[Dict[str, Any]] = None,
    validate_only: bool = False,
    conn: Optional[Any] = None,
) -> tuple[Dict[str, Any], List[str]]:
    now_ms = int(time.time() * 1000)
    errors: List[str] = []

    raw = policy_in if isinstance(policy_in, dict) else {}
    is_update = existing is not None

    policy_id = existing.get("id") if is_update else raw.get("id")
    if not isinstance(policy_id, str) or not policy_id.strip():
        policy_id = _next_id("pol") if not is_update else existing.get("id")
    policy_id = str(policy_id)

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name is required")
        name = "New policy" if not is_update else str(existing.get("name") or "")
    name = str(name).strip()

    status = raw.get("status") if is_update or "status" in raw else "draft"
    if not isinstance(status, str) or status not in ALLOWED_POLICY_STATUSES:
        errors.append("status must be one of draft|active|archived")
        status = "draft" if not is_update else str(existing.get("status") or "draft")

    enabled_raw = raw.get("enabled") if "enabled" in raw else (existing.get("enabled") if is_update else False)
    enabled = _coerce_bool(enabled_raw, default=False, errors=errors, field="enabled")

    mode = raw.get("mode") if "mode" in raw else (existing.get("mode") if is_update else "ADVISE_ONLY")
    if not isinstance(mode, str) or mode not in ALLOWED_POLICY_MODES:
        errors.append("mode must be ADVISE_ONLY|AUTO_EXECUTE")
        mode = "ADVISE_ONLY" if not is_update else str(existing.get("mode") or "ADVISE_ONLY")

    priority_raw = raw.get("priority") if "priority" in raw else (existing.get("priority") if is_update else 100)
    priority = _coerce_int(priority_raw, default=100, errors=errors, field="priority")
    if priority < 0:
        errors.append("priority must be >= 0")
        priority = max(0, priority)

    description = raw.get("description")
    if description is not None and not isinstance(description, str):
        errors.append("description must be a string")
        description = None

    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        errors.append("notes must be a string")
        notes = None

    created_by = raw.get("createdBy") if "createdBy" in raw else (existing.get("createdBy") if is_update else None)
    if created_by is not None and not isinstance(created_by, str):
        errors.append("createdBy must be a string")
        created_by = None

    updated_by = raw.get("updatedBy") if "updatedBy" in raw else (existing.get("updatedBy") if is_update else None)
    if updated_by is not None and not isinstance(updated_by, str):
        errors.append("updatedBy must be a string")
        updated_by = None

    scope = _normalize_scope(raw.get("scope"), existing.get("scope") if is_update else None, errors)
    conditions = _normalize_conditions(
        raw.get("conditions"), existing.get("conditions") if is_update else None, errors
    )
    actions = _normalize_actions(raw.get("actions"), existing.get("actions") if is_update else None, errors, conn)
    guardrails = _normalize_guardrails(
        raw.get("guardrails"), existing.get("guardrails") if is_update else None, errors
    )

    # Minimal semantic validation (mirrors frontend).
    if scope.get("type") == "nodes":
        ids = scope.get("nodeIds")
        if not isinstance(ids, list) or len(ids) == 0:
            errors.append("scope requires at least one node id")
    if status == "active":
        items = (conditions.get("items") or []) if isinstance(conditions, dict) else []
        if isinstance(items, list) and len(items) == 0:
            errors.append("active policy needs conditions")
        if len(actions) == 0:
            errors.append("active policy needs at least one action")

    risk_level = compute_risk_level(actions, conn)
    require_approval = guardrails.get("requireApproval")
    if not isinstance(require_approval, bool):
        require_approval = False
    guardrails = {
        **guardrails,
        "requireApproval": bool(require_approval),
    }

    created_at = existing.get("createdAt") if is_update else now_ms
    if not isinstance(created_at, int):
        created_at = now_ms
    updated_at = now_ms

    version = int(existing.get("version") or 1) + 1 if is_update else 1

    normalized: Dict[str, Any] = {
        "id": policy_id,
        "name": name,
        "description": description,
        "notes": notes,
        "version": version,
        "status": status,
        "enabled": bool(enabled),
        "mode": str(mode),
        "priority": int(priority),
        "scope": scope,
        "conditions": conditions,
        "actions": actions,
        "guardrails": guardrails,
        "createdAt": int(created_at),
        "updatedAt": int(updated_at),
        "createdBy": created_by,
        "updatedBy": updated_by,
        "riskLevel": int(risk_level),
    }

    if validate_only:
        # Avoid generating ids during validate-only calls.
        if existing is None and "id" not in raw:
            normalized["id"] = "pol-preview"
    return normalized, errors


def _default_policies() -> List[Dict[str, Any]]:
    base_guardrails = {"cooldownSec": 5, "maxPerHour": 1000, "requireApproval": False}
    return [
        {
            "id": "pol-auto-temp",
            "name": "Auto: Temp high",
            "status": "active",
            "enabled": True,
            "mode": "AUTO_EXECUTE",
            "priority": 10,
            "scope": {"type": "all"},
            "conditions": {
                "op": "AND",
                "items": [
                    {"metric": "temp", "op": ">", "value": 80, "durationSec": 0}
                ],
            },
            "actions": [
                {"type": "enableCooling"},
                {"type": "throttle"},
                {"type": "restart"},
                {"type": "reroute"},
            ],
            "guardrails": base_guardrails,
        },
        {
            "id": "pol-auto-error",
            "name": "Auto: Error rate high",
            "status": "active",
            "enabled": True,
            "mode": "AUTO_EXECUTE",
            "priority": 20,
            "scope": {"type": "all"},
            "conditions": {
                "op": "AND",
                "items": [
                    {
                        "metric": "error_rate",
                        "op": ">",
                        "value": 5,
                        "durationSec": 0,
                    }
                ],
            },
            "actions": [
                {"type": "restart"},
                {"type": "enableCooling"},
                {"type": "reroute"},
                {"type": "throttle"},
            ],
            "guardrails": base_guardrails,
        },
        {
            "id": "pol-auto-health",
            "name": "Auto: Health low",
            "status": "active",
            "enabled": True,
            "mode": "AUTO_EXECUTE",
            "priority": 30,
            "scope": {"type": "all"},
            "conditions": {
                "op": "AND",
                "items": [
                    {"metric": "health", "op": "<", "value": 60, "durationSec": 0}
                ],
            },
            "actions": [
                {"type": "restart"},
                {"type": "throttle"},
                {"type": "enableCooling"},
                {"type": "reroute"},
            ],
            "guardrails": base_guardrails,
        },
        {
            "id": "pol-auto-load",
            "name": "Auto: Sustained load",
            "status": "active",
            "enabled": True,
            "mode": "AUTO_EXECUTE",
            "priority": 40,
            "scope": {"type": "all"},
            "conditions": {
                "op": "AND",
                "items": [
                    {"metric": "load", "op": ">", "value": 95, "durationSec": 10}
                ],
            },
            "actions": [
                {"type": "reroute"},
                {"type": "throttle"},
            ],
            "guardrails": {"cooldownSec": 12, "maxPerHour": 1000, "requireApproval": False},
        },
    ]


def compute_risk_level(actions: List[Dict[str, Any]], conn: Any) -> int:
    max_risk = 0
    for step in actions:
        action_type = step.get("type") if isinstance(step, dict) else None
        spec = action_catalog.get_action(str(action_type), conn) if action_type else None
        risk = spec.risk_level if spec else 3
        max_risk = max(max_risk, int(risk))
    return int(max(0, min(3, max_risk)))


def _normalize_scope(raw: Any, existing: Any, errors: List[str]) -> Dict[str, Any]:
    scope = raw if isinstance(raw, dict) else (existing if isinstance(existing, dict) else {"type": "all"})
    scope_type = scope.get("type")
    if not isinstance(scope_type, str) or scope_type not in ALLOWED_SCOPE_TYPES:
        errors.append("scope.type must be all|nodes|tag|group")
        scope_type = "all"

    out: Dict[str, Any] = {"type": scope_type}
    if scope_type == "nodes":
        node_ids = scope.get("nodeIds")
        if not isinstance(node_ids, list):
            node_ids = []
        out["nodeIds"] = [str(v) for v in node_ids if isinstance(v, str) and v.strip()]
    if scope_type in {"tag", "group"}:
        selector = scope.get("selector")
        if selector is not None and not isinstance(selector, dict):
            errors.append("scope.selector must be an object")
            selector = None
        if isinstance(selector, dict):
            key = selector.get("key")
            values = selector.get("values")
            if key is not None and not isinstance(key, str):
                errors.append("scope.selector.key must be a string")
                key = None
            if values is not None and not isinstance(values, list):
                errors.append("scope.selector.values must be a list")
                values = []
            out["selector"] = {
                "key": str(key or ""),
                "values": [str(v) for v in (values or []) if isinstance(v, str) and v.strip()],
            }
    return out


def _normalize_conditions(raw: Any, existing: Any, errors: List[str]) -> Dict[str, Any]:
    conditions = raw if isinstance(raw, dict) else (existing if isinstance(existing, dict) else {"op": "AND", "items": []})
    op = conditions.get("op")
    if not isinstance(op, str) or op not in ALLOWED_CONDITION_GROUP_OPS:
        errors.append("conditions.op must be AND|OR")
        op = "AND"
    items_raw = conditions.get("items")
    if not isinstance(items_raw, list):
        errors.append("conditions.items must be a list")
        items_raw = []

    items: List[Dict[str, Any]] = []
    for idx, cond in enumerate(items_raw):
        if not isinstance(cond, dict):
            errors.append(f"conditions.items[{idx}] must be an object")
            continue
        metric = cond.get("metric")
        op_raw = cond.get("op")
        value_raw = cond.get("value")
        duration_raw = cond.get("durationSec")

        if not isinstance(metric, str) or metric not in ALLOWED_CONDITION_METRICS:
            errors.append(f"conditions.items[{idx}].metric invalid")
            continue
        if not isinstance(op_raw, str) or op_raw not in ALLOWED_CONDITION_OPS:
            errors.append(f"conditions.items[{idx}].op invalid")
            continue
        if not _is_number(value_raw):
            errors.append(f"conditions.items[{idx}].value must be a number")
            continue

        value = float(value_raw) if isinstance(value_raw, (int, float)) and not isinstance(value_raw, bool) else 0.0
        item: Dict[str, Any] = {"metric": metric, "op": op_raw, "value": value}
        if duration_raw is not None:
            duration_value = float(duration_raw) if _is_number(duration_raw) else None
            if duration_value is None or duration_value < 0:
                errors.append(f"conditions.items[{idx}].durationSec must be >= 0")
            else:
                item["durationSec"] = duration_value
        items.append(item)

    return {"op": op, "items": items}


def _normalize_actions(raw: Any, existing: Any, errors: List[str], conn: Any) -> List[Dict[str, Any]]:
    actions_raw = raw if isinstance(raw, list) else (existing if isinstance(existing, list) else [])
    actions: List[Dict[str, Any]] = []
    for idx, step in enumerate(actions_raw):
        if not isinstance(step, dict):
            errors.append(f"actions[{idx}] must be an object")
            continue
        action_type = step.get("type")
        if not isinstance(action_type, str) or not action_type.strip():
            errors.append(f"actions[{idx}].type is required")
            continue
        spec = action_catalog.get_action(action_type, conn)
        if spec is None:
            errors.append(f"actions[{idx}].type is invalid")
            continue
        capability = step.get("capability")
        availability = step.get("availability")
        if capability is not None and (not isinstance(capability, str) or capability not in ALLOWED_ACTION_CAPABILITIES):
            errors.append(f"actions[{idx}].capability invalid")
            capability = None
        if availability is not None and (not isinstance(availability, str) or availability not in ALLOWED_ACTION_AVAILABILITIES):
            errors.append(f"actions[{idx}].availability invalid")
            availability = None
        params = step.get("params")
        if params is not None and not isinstance(params, dict):
            errors.append(f"actions[{idx}].params must be an object")
            params = None

        out: Dict[str, Any] = {
            "type": action_type,
            "capability": capability or spec.capability,
            "availability": availability or spec.availability,
        }
        if params is not None:
            out["params"] = params
        actions.append(out)
    return actions


def _normalize_guardrails(raw: Any, existing: Any, errors: List[str]) -> Dict[str, Any]:
    guard = raw if isinstance(raw, dict) else (existing if isinstance(existing, dict) else {})
    cooldown = guard.get("cooldownSec", 60)
    max_per_hour = guard.get("maxPerHour", 12)
    require_approval = guard.get("requireApproval", False)

    if not _is_number(cooldown) or float(cooldown) < 0:
        errors.append("guardrails.cooldownSec must be >= 0")
        cooldown = 60
    if not isinstance(max_per_hour, int) or isinstance(max_per_hour, bool) or max_per_hour < 0:
        errors.append("guardrails.maxPerHour must be an integer >= 0")
        max_per_hour = 12
    if not isinstance(require_approval, bool):
        errors.append("guardrails.requireApproval must be boolean")
        require_approval = False

    return {
        "cooldownSec": float(cooldown),
        "maxPerHour": int(max_per_hour),
        "requireApproval": bool(require_approval),
    }


def _coerce_bool(value: Any, default: bool, errors: List[str], field: str) -> bool:
    if isinstance(value, bool):
        return bool(value)
    if value is None:
        return bool(default)
    errors.append(f"{field} must be boolean")
    return bool(default)


def _coerce_int(value: Any, default: int, errors: List[str], field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float) and not isinstance(value, bool) and value.is_integer():
        return int(value)
    if value is None:
        return int(default)
    errors.append(f"{field} must be an integer")
    return int(default)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _loads_json(raw: Any) -> Any:
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def _next_id(prefix: str) -> str:
    global _POLICY_ID_COUNTER
    with _POLICY_ID_LOCK:
        _POLICY_ID_COUNTER += 1
        return f"{prefix}-{int(time.time() * 1000)}-{_POLICY_ID_COUNTER}"
