from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

from app.persistence import db

ALLOWED_EVENT_TYPES = {
    "fault",
    "incident",
    "action",
    "ai",
    "autonomy",
    "reset",
    "policy",
    "agent",
    "node",
    "operation",
    "load_balancer",
    "project",
}
ALLOWED_FAULT_TYPES = {"overheat", "hardware_fail", "network_spike"}
ALLOWED_ACTIONS: Set[str] = set()
ALLOWED_INCIDENT_METRICS = {"temp", "error_rate", "health", "load"}


def append_event(
    tick: int,
    event_type: str,
    message: str,
    payload: Dict[str, Any],
    conn: Optional[Any] = None,
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"invalid event type: {event_type}")
    if not isinstance(tick, int):
        raise ValueError("tick must be int")
    if not isinstance(message, str):
        raise ValueError("message must be str")

    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    _validate_payload(event_type, payload)

    timestamp = ts or _iso_now()
    payload_json = json.dumps(payload, ensure_ascii=True)
    if db.is_postgres(conn):
        cursor = conn.execute(
            "INSERT INTO events (tick, ts, type, message, payload) VALUES (?, ?, ?, ?, ?) RETURNING id",
            (tick, timestamp, event_type, message, payload_json),
        )
        row = cursor.fetchone() or {}
        event_id = int(row.get("id", 0)) if isinstance(row, dict) else int(row[0])
    else:
        cursor = conn.execute(
            "INSERT INTO events (tick, ts, type, message, payload) VALUES (?, ?, ?, ?, ?)",
            (tick, timestamp, event_type, message, payload_json),
        )
        event_id = int(cursor.lastrowid or 0)
    conn.commit()

    event = {
        "id": event_id,
        "tick": tick,
        "ts": timestamp,
        "type": event_type,
        "message": message,
        "payload": payload,
    }

    if close_conn:
        conn.close()

    return event


def list_events(
    limit: Optional[int] = None,
    since_tick: Optional[int] = None,
    after_id: Optional[int] = None,
    types: Optional[Iterable[str]] = None,
    targets: Optional[Iterable[str]] = None,
    conn: Optional[Any] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    type_list = _normalize_list(types)
    target_list = _normalize_list(targets)

    sql = "SELECT id, tick, ts, type, message, payload FROM events"
    conditions: List[str] = []
    params: List[Any] = []

    if since_tick is not None:
        conditions.append("tick >= ?")
        params.append(int(since_tick))
    if after_id is not None:
        conditions.append("id > ?")
        params.append(int(after_id))
    if type_list:
        placeholders = ",".join(["?"] * len(type_list))
        conditions.append(f"type IN ({placeholders})")
        params.extend(type_list)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    query_order = "ASC"
    if limit is not None and after_id is None:
        # Without an anchor, default to returning the most recent N events.
        # We still return events in ascending order to preserve timeline rendering.
        query_order = "DESC"
    sql += f" ORDER BY id {query_order}"

    cursor = conn.execute(sql, params)

    events: List[Dict[str, Any]] = []
    for row in cursor:
        event = _row_to_event(row)
        if target_list:
            payload_target = None
            payload = event.get("payload")
            if isinstance(payload, dict):
                payload_target = payload.get("target")
            if payload_target not in target_list:
                continue
        events.append(event)
        if limit is not None and len(events) >= limit:
            break

    if query_order == "DESC":
        events.reverse()

    if close_conn:
        conn.close()

    return {"events": events}


def clear_events(conn: Optional[Any] = None) -> None:
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)
    db.clear_events(conn)
    if close_conn:
        conn.close()


def _row_to_event(row: Any) -> Dict[str, Any]:
    payload: Any = {}
    if row["payload"]:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}

    return {
        "id": row["id"],
        "tick": row["tick"],
        "ts": row["ts"],
        "type": row["type"],
        "message": row["message"],
        "payload": payload,
    }


def _normalize_list(values: Optional[Iterable[str]]) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        return [item.strip() for item in values.split(",") if item.strip()]
    normalized: List[str] = []
    for item in values:
        if item is None:
            continue
        item_str = str(item).strip()
        if item_str:
            normalized.append(item_str)
    return normalized


def _validate_payload(event_type: str, payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload must be dict")

    if event_type == "fault":
        _require_keys(payload, {"type", "target"})
        fault_type = payload.get("type")
        if fault_type not in ALLOWED_FAULT_TYPES:
            raise ValueError(f"invalid fault type: {fault_type}")
        _require_str(payload, "target")
        return

    if event_type == "incident":
        _require_keys(payload, {"target", "metric", "value", "threshold"})
        metric = payload.get("metric")
        if metric not in ALLOWED_INCIDENT_METRICS:
            raise ValueError(f"invalid incident metric: {metric}")
        _require_str(payload, "target")
        _require_number(payload, "value")
        _require_number(payload, "threshold")
        return

    if event_type == "action":
        _require_keys(payload, {"action"})
        action = payload.get("action")
        if not isinstance(action, str) or not action.strip():
            raise ValueError("payload.action must be str")
        if "target" in payload:
            _require_str(payload, "target")
        return

    if event_type == "policy":
        _require_keys(
            payload,
            {"policy_id", "policy_name", "policy_version", "mode", "target", "decision"},
        )
        _require_str(payload, "policy_id")
        _require_str(payload, "policy_name")
        if not isinstance(payload.get("policy_version"), int):
            raise ValueError("payload.policy_version must be int")
        _require_str(payload, "mode")
        _require_str(payload, "target")
        _require_str(payload, "decision")
        # Optional fields
        if "actions" in payload and not isinstance(payload.get("actions"), list):
            raise ValueError("payload.actions must be list")
        if "reasons" in payload and not isinstance(payload.get("reasons"), list):
            raise ValueError("payload.reasons must be list")
        return

    if event_type == "ai":
        _require_exact_keys(
            payload,
            {"root_causes", "recommended_actions", "risks", "rollback_conditions"},
        )
        for key in payload:
            _require_list_of_str(payload, key)
        return

    if event_type == "autonomy":
        _require_keys(payload, {"enabled"})
        if not isinstance(payload.get("enabled"), bool):
            raise ValueError("autonomy.enabled must be bool")
        return

    if event_type == "reset":
        _require_keys(payload, {"reset_events"})
        if not isinstance(payload.get("reset_events"), bool):
            raise ValueError("reset.reset_events must be bool")
        return

    if event_type in {"agent", "node", "operation", "load_balancer", "project"}:
        return


def _require_keys(payload: Dict[str, Any], keys: Set[str]) -> None:
    missing = keys - set(payload.keys())
    if missing:
        raise ValueError(f"payload missing keys: {sorted(missing)}")


def _require_exact_keys(payload: Dict[str, Any], keys: Set[str]) -> None:
    if set(payload.keys()) != keys:
        raise ValueError("payload keys do not match schema")


def _require_str(payload: Dict[str, Any], key: str) -> None:
    if not isinstance(payload.get(key), str):
        raise ValueError(f"payload.{key} must be str")


def _require_number(payload: Dict[str, Any], key: str) -> None:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"payload.{key} must be number")


def _require_list_of_str(payload: Dict[str, Any], key: str) -> None:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"payload.{key} must be list")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"payload.{key} items must be str")


def _iso_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
