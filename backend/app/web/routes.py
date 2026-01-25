from __future__ import annotations

from typing import Any, List, Optional

from flask import Blueprint, jsonify, request

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
    limit = _parse_optional_int(request.args.get("limit"))
    since_tick = _parse_optional_int(request.args.get("since_tick"))
    types = _parse_query_list("type")
    targets = _parse_query_list("target")
    result = event_service.list_events(
        limit=limit,
        since_tick=since_tick,
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
