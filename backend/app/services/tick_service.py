from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from app.services import autonomy_service, event_service

DEFAULT_SERVERS = {
    "S1": {
        "load": 0.0,
        "temp": 25.0,
        "error_rate": 0.0,
        "power": 80.0,
        "health": 100,
        "cooling": False,
    },
    "S2": {
        "load": 0.0,
        "temp": 25.0,
        "error_rate": 0.0,
        "power": 80.0,
        "health": 100,
        "cooling": False,
    },
    "S3": {
        "load": 0.0,
        "temp": 25.0,
        "error_rate": 0.0,
        "power": 80.0,
        "health": 100,
        "cooling": False,
    },
}

ALLOWED_FAULT_TYPES = {"overheat", "hardware_fail", "network_spike"}
ALLOWED_TARGETS = {"S1", "S2", "S3"}

_WORLD_STATE: Dict[str, Any] = {}
_ACTIVE_FAULTS: List[Dict[str, Any]] = []


def get_state() -> Dict[str, Any]:
    state = _ensure_state()
    state["autonomy_enabled"] = autonomy_service.is_autonomy_enabled()
    return deepcopy(state)


def get_tick() -> int:
    return int(_ensure_state().get("tick", 0))


def advance(steps: int = 1) -> Dict[str, Any]:
    global _WORLD_STATE
    state = _ensure_state()
    for _ in range(steps):
        state["tick"] = int(state.get("tick", 0)) + 1
        _apply_stub_physics(state, _ACTIVE_FAULTS)
        state = autonomy_service.on_tick(state, execute_action_fn=_execute_action)
        _WORLD_STATE = state
    state["autonomy_enabled"] = autonomy_service.is_autonomy_enabled()
    return deepcopy(state)


def inject_fault(fault_type: str, target: str) -> None:
    if fault_type not in ALLOWED_FAULT_TYPES:
        raise ValueError("invalid fault type")
    if target not in ALLOWED_TARGETS:
        raise ValueError("invalid target")
    state = _ensure_state()
    _ACTIVE_FAULTS.append({"type": fault_type, "target": target})
    event_service.append_event(
        tick=int(state.get("tick", 0)),
        event_type="fault",
        message=f"fault {fault_type} injected on {target}",
        payload={"type": fault_type, "target": target},
    )


def reset(reset_events: bool = True) -> Dict[str, Any]:
    _reset_state()
    if reset_events:
        event_service.clear_events()
    else:
        event_service.append_event(
            tick=0,
            event_type="reset",
            message="world reset",
            payload={"reset_events": False},
        )
    return get_state()


def _ensure_state() -> Dict[str, Any]:
    global _WORLD_STATE
    if not _WORLD_STATE:
        _WORLD_STATE = _default_world_state()
    return _WORLD_STATE


def _reset_state() -> None:
    global _WORLD_STATE, _ACTIVE_FAULTS
    _WORLD_STATE = _default_world_state()
    _ACTIVE_FAULTS = []


def _default_world_state() -> Dict[str, Any]:
    return {
        "tick": 0,
        "incoming_traffic": 0,
        "servers": deepcopy(DEFAULT_SERVERS),
        "autonomy_enabled": autonomy_service.is_autonomy_enabled(),
    }


def _execute_action(
    world_state: Dict[str, Any],
    action: str,
    target: Optional[str],
) -> Dict[str, Any]:
    # TODO (Member B): Replace with simulator action execution once core
    # world model is implemented under backend/app/core/simulator/.
    servers = world_state.get("servers")
    if not servers or not target or target not in servers:
        return world_state
    server = servers[target]

    if action == "enableCooling":
        server["cooling"] = True
    elif action == "disableCooling":
        server["cooling"] = False
    elif action == "restart":
        server["temp"] = 70.0
        server["error_rate"] = 0.0
    elif action == "throttle":
        incoming = world_state.get("incoming_traffic", 0)
        if isinstance(incoming, (int, float)) and not isinstance(incoming, bool):
            world_state["incoming_traffic"] = max(0, incoming - 10)
    elif action == "reroute":
        _reroute_load(servers, target)

    return world_state


def _apply_stub_physics(state: Dict[str, Any], faults: List[Dict[str, Any]]) -> None:
    # TODO (Member B): Replace with simulator tick rules (docs/00_PROJECT_CONTEXT.md).
    servers = state.get("servers", {})
    faults_by_target = _group_faults(faults)

    for target, server in servers.items():
        load = _as_number(server.get("load"), 0.0)
        temp = _as_number(server.get("temp"), 25.0)
        error_rate = _as_number(server.get("error_rate"), 0.0)
        health = _as_number(server.get("health"), 100.0)
        cooling = bool(server.get("cooling"))

        cooling_effect = 5.0 if cooling else 0.0
        natural_cooling = 1.0
        temp += 0.02 * load - cooling_effect - natural_cooling

        for fault in faults_by_target.get(target, []):
            if fault["type"] == "overheat":
                temp += 3.0
            elif fault["type"] == "hardware_fail":
                error_rate += 2.0
            elif fault["type"] == "network_spike":
                load = min(100.0, load + 30.0)

        if temp > 70.0:
            error_rate += (temp - 70.0) * 0.02
        else:
            error_rate *= 0.95

        health -= (max(0.0, temp - 70.0) * 0.2 + error_rate * 0.5)
        health += 0.2

        server["load"] = _clamp(load, 0.0, 100.0)
        server["temp"] = temp
        server["error_rate"] = max(0.0, error_rate)
        server["health"] = int(_clamp(health, 0.0, 100.0))
        server["power"] = 80.0 + server["load"] * 2.0 + (40.0 if cooling else 0.0)


def _reroute_load(servers: Dict[str, Any], target: str) -> None:
    target_state = servers.get(target)
    if not isinstance(target_state, dict):
        return
    target_load = _as_number(target_state.get("load"), 0.0)
    reduction = min(10.0, target_load)
    target_state["load"] = max(0.0, target_load - reduction)

    others = [key for key in servers.keys() if key != target]
    if not others:
        return
    per_server = reduction / len(others)
    for key in others:
        state = servers.get(key)
        if not isinstance(state, dict):
            continue
        load = _as_number(state.get("load"), 0.0)
        state["load"] = min(100.0, load + per_server)


def _group_faults(faults: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for fault in faults:
        target = fault.get("target")
        if target is None:
            continue
        grouped.setdefault(str(target), []).append(fault)
    return grouped


def _as_number(value: Any, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return float(default)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
