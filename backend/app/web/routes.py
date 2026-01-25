from __future__ import annotations

from typing import Any, List, Optional

from flask import Blueprint, jsonify, request

from app.core.simulator.world import SERVER_IDS
from app.services import autonomy_service, event_service, tick_service

bp = Blueprint("api", __name__, url_prefix="/api")

#if teammate B upload their function, update any about tick_service helper function here
@bp.get("/state")
def get_state():
    return jsonify(tick_service.get_state())


@bp.post("/tick")
def post_tick():
    body = request.get_json(silent=True) or {}
    steps = body.get("steps", 1)
    if not _is_positive_int(steps):
        return _bad_request("steps must be a positive integer")
    return jsonify(tick_service.advance(int(steps)))


@bp.post("/fault")
def post_fault():
    body = request.get_json(silent=True) or {}
    fault_type = body.get("type")
    target = body.get("target")
    if not isinstance(fault_type, str) or not isinstance(target, str):
        return _bad_request("type and target are required")
    try:
        tick_service.inject_fault(fault_type, target)   #if teammate B update inject_fault, renew condition here
    except ValueError as exc:
        return _bad_request(str(exc))
    return jsonify({"ok": True})


@bp.get("/events")
def get_events():
    limit_raw = request.args.get("limit")
    limit = _parse_optional_int(limit_raw)
    if limit_raw is not None:
        if limit is None or limit <= 0:
            return _bad_request("limit must be a positive integer")
        if limit > 1000:
            return _bad_request("limit must be <= 1000")

    since_tick_raw = request.args.get("since_tick")
    since_tick = _parse_optional_int(since_tick_raw)
    if since_tick_raw is not None:
        if since_tick is None or since_tick < 0:
            return _bad_request("since_tick must be a non-negative integer")

    after_id_raw = request.args.get("after_id")
    after_id = _parse_optional_int(after_id_raw)
    if after_id_raw is not None:
        if after_id is None or after_id < 0:
            return _bad_request("after_id must be a non-negative integer")

    types = _parse_query_list("type")
    if types and any(t not in event_service.ALLOWED_EVENT_TYPES for t in types):
        return _bad_request("type contains invalid event type")
    targets = _parse_query_list("target")
    if targets and any(t not in SERVER_IDS for t in targets):
        return _bad_request("target contains invalid server id")
    result = event_service.list_events(
        limit=limit,
        since_tick=since_tick,
        after_id=after_id,
        types=types,
        targets=targets,
    )
    return jsonify(result)


@bp.post("/autonomy")
def post_autonomy():
    body = request.get_json(silent=True) or {}
    if "enabled" not in body or not isinstance(body.get("enabled"), bool):
        return _bad_request("enabled must be boolean")
    enabled = autonomy_service.set_autonomy_enabled(body["enabled"], tick=tick_service.get_tick())
    return jsonify({"enabled": enabled})


@bp.post("/reset")
def post_reset():
    body = request.get_json(silent=True) or {}
    reset_events = body.get("reset_events", True)
    if not isinstance(reset_events, bool):
        return _bad_request("reset_events must be boolean")
    return jsonify(tick_service.reset(reset_events=reset_events))


def _bad_request(message: str):
    return jsonify({"error": {"code": "BAD_REQUEST", "message": message}}), 400


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed


def _parse_query_list(key: str) -> List[str]:
    values = request.args.getlist(key)
    if values:
        return values
    single = request.args.get(key)
    if single is None:
        return []
    return [value.strip() for value in single.split(",") if value.strip()]
