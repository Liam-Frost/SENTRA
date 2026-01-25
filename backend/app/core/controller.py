from __future__ import annotations

from typing import Any, Dict, List, Optional

INCIDENT_THRESHOLDS = {
    "temp": 80.0,
    "error_rate": 5.0,
    "health": 60.0,
    "load": 85.0,
}

ACTION_PRIORITY = ["enableCooling", "reroute", "throttle", "restart"]
ACTION_PRIORITY_BY_METRIC = {
    "temp": ["enableCooling", "throttle", "restart", "reroute"],
    "error_rate": ["restart", "enableCooling", "reroute", "throttle"],
    "health": ["restart", "throttle", "enableCooling", "reroute"],
    "load": ["reroute", "throttle", "enableCooling"],
}


def detect_incidents(world_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    incidents: List[Dict[str, Any]] = []
    servers = (world_state or {}).get("servers", {})
    for target, state in servers.items():
        status = str(state.get("status") or "running")
        if status in {"booting", "restarting", "thermal_shutdown", "off"}:
            continue
        temp = _as_number(state.get("temp"), 0.0)
        error_rate = _as_number(state.get("error_rate"), 0.0)
        health = _as_number(state.get("health"), 100.0)
        load = _as_number(state.get("load"), 0.0)

        if temp > INCIDENT_THRESHOLDS["temp"]:
            incidents.append(
                {
                    "target": target,
                    "metric": "temp",
                    "value": temp,
                    "threshold": INCIDENT_THRESHOLDS["temp"],
                    "message": f"temp > 80 on {target}",
                }
            )
        if error_rate > INCIDENT_THRESHOLDS["error_rate"]:
            incidents.append(
                {
                    "target": target,
                    "metric": "error_rate",
                    "value": error_rate,
                    "threshold": INCIDENT_THRESHOLDS["error_rate"],
                    "message": f"error_rate > 5 on {target}",
                }
            )
        if health < INCIDENT_THRESHOLDS["health"]:
            incidents.append(
                {
                    "target": target,
                    "metric": "health",
                    "value": health,
                    "threshold": INCIDENT_THRESHOLDS["health"],
                    "message": f"health < 60 on {target}",
                }
            )
        if load > INCIDENT_THRESHOLDS["load"]:
            incidents.append(
                {
                    "target": target,
                    "metric": "load",
                    "value": load,
                    "threshold": INCIDENT_THRESHOLDS["load"],
                    "message": f"load > 85 on {target}",
                }
            )
    return incidents


def select_action(
    world_state: Dict[str, Any],
    incident: Dict[str, Any],
    last_action: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    target = incident.get("target")
    server_state = (world_state or {}).get("servers", {}).get(target, {})
    if server_state.get("status") not in (None, "running"):
        return None

    metric = str(incident.get("metric") or "")
    priority = ACTION_PRIORITY_BY_METRIC.get(metric, ACTION_PRIORITY)

    start_index = 0
    if last_action in priority and last_action != priority[-1]:
        start_index = priority.index(last_action) + 1

    for action in priority[start_index:]:
        decision = _evaluate_action(action, server_state, world_state, target)
        if decision is not None:
            return decision

    return None


def is_restart_safe(server_state: Dict[str, Any]) -> bool:
    temp = _as_number(server_state.get("temp"), 0.0)
    error_rate = _as_number(server_state.get("error_rate"), 0.0)
    return temp < 85.0 and error_rate > 5.0


def _evaluate_action(
    action: str,
    server_state: Dict[str, Any],
    world_state: Dict[str, Any],
    target: Optional[str],
) -> Optional[Dict[str, Any]]:
    if action == "enableCooling":
        if server_state.get("cooling") is True:
            return None
        return _decision(action, target)

    if action == "reroute":
        return _decision(action, target)

    if action == "throttle":
        return _decision(action, target)

    if action == "restart":
        if is_restart_safe(server_state):
            return _decision(action, target)
        temp = _as_number(server_state.get("temp"), 0.0)
        error_rate = _as_number(server_state.get("error_rate"), 0.0)
        reason = (
            "restart unsafe: temp >= 85 or error_rate <= 5 "
            f"(temp={temp}, error_rate={error_rate})"
        )
        return _decision(action, target, blocked=True, reason=reason)

    return None


def _decision(
    action: str,
    target: Optional[str],
    blocked: bool = False,
    reason: str = "",
) -> Dict[str, Any]:
    return {
        "action": action,
        "target": target,
        "blocked": blocked,
        "reason": reason,
    }


def _as_number(value: Any, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return float(default)
