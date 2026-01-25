from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from app.core import controller
from app.core.ai import ai_client
from app.services import event_service

WAIT_TICKS = 5
AI_COOLDOWN_TICKS = 10
HIGH_LOAD_THRESHOLD = 95.0
HIGH_LOAD_TICKS = 10
HIGH_LOAD_FORCE_COOLDOWN = 12
BLOCKED_EVENT_COOLDOWN = 30


@dataclass
class TargetState:
    last_action: Optional[str] = None
    last_action_tick: Optional[int] = None


@dataclass
class AutonomyState:
    enabled: bool = False
    targets: Dict[str, TargetState] = field(default_factory=dict)
    last_tick_processed: Optional[int] = None
    active_incidents: Set[str] = field(default_factory=set)
    last_ai_tick: Optional[int] = None
    high_load_ticks: Dict[str, int] = field(default_factory=dict)
    last_forced_tick: Dict[str, int] = field(default_factory=dict)
    last_forced_action: Dict[str, str] = field(default_factory=dict)
    last_blocked_action: Dict[str, int] = field(default_factory=dict)


_STATE = AutonomyState()
_STATE_LOCK = threading.RLock()


def set_autonomy_enabled(enabled: bool, tick: Optional[int] = None, conn: Any = None) -> bool:
    with _STATE_LOCK:
        _STATE.enabled = bool(enabled)
        if not _STATE.enabled:
            _STATE.targets.clear()
            _STATE.last_tick_processed = None
            _STATE.active_incidents.clear()
            _STATE.last_ai_tick = None
            _STATE.high_load_ticks.clear()
            _STATE.last_forced_tick.clear()
            _STATE.last_forced_action.clear()
            _STATE.last_blocked_action.clear()
        else:
            _STATE.active_incidents.clear()
            _STATE.last_ai_tick = None
            _STATE.high_load_ticks.clear()
            _STATE.last_forced_tick.clear()
            _STATE.last_forced_action.clear()
            _STATE.last_blocked_action.clear()
        event_service.append_event(
            tick=_safe_tick(tick),
            event_type="autonomy",
            message=f"autonomy {'enabled' if enabled else 'disabled'}",
            payload={"enabled": bool(enabled)},
            conn=conn,
        )
        return _STATE.enabled


def is_autonomy_enabled() -> bool:
    with _STATE_LOCK:
        return _STATE.enabled


def process_autonomy(
    world_state: Dict[str, Any],
    execute_action_fn: Optional[Callable[[Dict[str, Any], str, Optional[str]], Any]] = None,
    ai_explainer_fn: Optional[Callable[[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]], Dict[str, Any]]] = None,
    conn: Any = None,
) -> Dict[str, Any]:
    with _STATE_LOCK:
        if not _STATE.enabled:
            return world_state

        tick = _safe_tick(world_state.get("tick"))
        if _STATE.last_tick_processed is not None:
            if tick < _STATE.last_tick_processed:
                _STATE.targets.clear()
                _STATE.last_tick_processed = None
            elif tick == _STATE.last_tick_processed:
                return world_state

        _update_high_load_ticks(world_state)
        incidents = controller.detect_incidents(world_state)
        incident_keys = {_incident_key(incident) for incident in incidents}
        new_incidents = [
            incident
            for incident in incidents
            if _incident_key(incident) not in _STATE.active_incidents
        ]

        for incident in new_incidents:
            event_service.append_event(
                tick=tick,
                event_type="incident",
                message=f"incident start: {incident['message']}",
                payload={
                    "target": incident["target"],
                    "metric": incident["metric"],
                    "value": incident["value"],
                    "threshold": incident["threshold"],
                    "status": "start",
                },
                conn=conn,
            )

        resolved_keys = _STATE.active_incidents - incident_keys
        for key in resolved_keys:
            target, metric = key.split(":", 1)
            value = _metric_value(world_state, target, metric)
            threshold = controller.INCIDENT_THRESHOLDS.get(metric, 0)
            event_service.append_event(
                tick=tick,
                event_type="incident",
                message=f"incident resolved: {metric} back to normal on {target}",
                payload={
                    "target": target,
                    "metric": metric,
                    "value": value,
                    "threshold": threshold,
                    "status": "resolved",
                },
                conn=conn,
            )

        _STATE.active_incidents = incident_keys
        active_targets = {incident["target"] for incident in incidents}
        _clear_inactive_targets(active_targets)

        decisions: List[Dict[str, Any]] = []
        forced_actions = _maybe_force_high_load_actions(
            world_state, tick, execute_action_fn, conn
        )
        decisions.extend(forced_actions)
        for target, incident in _group_incidents_by_target(incidents).items():
            last_state = _STATE.targets.get(target)
            if last_state and last_state.last_action_tick is not None:
                if tick - last_state.last_action_tick < WAIT_TICKS:
                    continue

            decision = controller.select_action(
                world_state=world_state,
                incident=incident,
                last_action=last_state.last_action if last_state else None,
            )
            if decision is None:
                continue
            decisions.append(decision)

            if decision["blocked"]:
                if _should_emit_blocked(decision["action"], target, tick):
                    event_service.append_event(
                        tick=tick,
                        event_type="action",
                        message=f"blocked {decision['action']} on {target}: {decision['reason']}",
                        payload={"action": decision["action"], "target": target},
                        conn=conn,
                    )
                continue

            world_state = _execute_action(
                world_state,
                decision["action"],
                target,
                execute_action_fn,
            )

            event_service.append_event(
                tick=tick,
                event_type="action",
                message=f"execute {decision['action']} on {target}",
                payload={"action": decision["action"], "target": target},
                conn=conn,
            )

            _STATE.targets[target] = TargetState(
                last_action=decision["action"],
                last_action_tick=tick,
            )

        if new_incidents:
            should_emit = (
                _STATE.last_ai_tick is None
                or tick - _STATE.last_ai_tick >= AI_COOLDOWN_TICKS
            )
            if should_emit:
                explainer = ai_explainer_fn or ai_client.explain_incidents
                ai_payload = explainer(world_state, new_incidents, decisions)
                event_service.append_event(
                    tick=tick,
                    event_type="ai",
                    message="ai explanation",
                    payload=ai_payload,
                    conn=conn,
                )
                _STATE.last_ai_tick = tick

        _STATE.last_tick_processed = tick
        return world_state


def on_tick(
    world_state: Dict[str, Any],
    execute_action_fn: Optional[Callable[[Dict[str, Any], str, Optional[str]], Any]] = None,
    ai_explainer_fn: Optional[Callable[[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]], Dict[str, Any]]] = None,
    conn: Any = None,
) -> Dict[str, Any]:
    return process_autonomy(world_state, execute_action_fn, ai_explainer_fn, conn)


def _execute_action(
    world_state: Dict[str, Any],
    action: str,
    target: Optional[str],
    execute_action_fn: Optional[Callable[[Dict[str, Any], str, Optional[str]], Any]],
) -> Dict[str, Any]:
    if execute_action_fn:
        result = execute_action_fn(world_state, action, target)
        return result if isinstance(result, dict) else world_state
    return _default_execute_action(world_state, action, target)


def _default_execute_action(
    world_state: Dict[str, Any],
    action: str,
    target: Optional[str],
) -> Dict[str, Any]:
    servers = world_state.get("servers") if isinstance(world_state, dict) else None
    if not servers or not target or target not in servers:
        return world_state
    server = servers[target]

    if action == "enableCooling":
        server["cooling"] = True
        server["cooling_level"] = max(float(server.get("cooling_level") or 0.0), 0.2)
        return world_state
    if action == "disableCooling":
        server["cooling"] = False
        server["cooling_level"] = 0.0
        return world_state
    return world_state


def _group_incidents_by_target(incidents: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for incident in incidents:
        target = incident.get("target")
        if not target:
            continue
        grouped.setdefault(target, []).append(incident)

    selected: Dict[str, Dict[str, Any]] = {}
    for target, target_incidents in grouped.items():
        selected[target] = _select_most_severe(target_incidents)
    return selected


def _clear_inactive_targets(active_targets: Set[str]) -> None:
    for target in list(_STATE.targets.keys()):
        if target not in active_targets:
            del _STATE.targets[target]


def _safe_tick(value: Optional[int]) -> int:
    if isinstance(value, int):
        return value
    return 0


def _as_number(value: Any, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return float(default)


def _select_most_severe(incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not incidents:
        return {}

    metric_priority = {"temp": 3, "error_rate": 2, "health": 1}

    def score(incident: Dict[str, Any]) -> float:
        metric = str(incident.get("metric") or "")
        value = _as_number(incident.get("value"), 0.0)
        threshold = _as_number(incident.get("threshold"), 1.0)
        if metric == "health":
            severity = max(0.0, (threshold - value) / threshold)
        else:
            severity = max(0.0, (value - threshold) / threshold)
        return severity

    incidents_sorted = sorted(
        incidents,
        key=lambda incident: (
            score(incident),
            metric_priority.get(str(incident.get("metric") or ""), 0),
        ),
        reverse=True,
    )
    return incidents_sorted[0]


def _incident_key(incident: Dict[str, Any]) -> str:
    target = str(incident.get("target") or "")
    metric = str(incident.get("metric") or "")
    return f"{target}:{metric}"


def _metric_value(world_state: Dict[str, Any], target: str, metric: str) -> float:
    server = (world_state or {}).get("servers", {}).get(target, {})
    value = server.get(metric)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _update_high_load_ticks(world_state: Dict[str, Any]) -> None:
    servers = (world_state or {}).get("servers", {})
    for target, server in servers.items():
        status = server.get("status")
        if status not in (None, "running"):
            _STATE.high_load_ticks[target] = 0
            continue
        load = _as_number(server.get("load"), 0.0)
        if load >= HIGH_LOAD_THRESHOLD:
            _STATE.high_load_ticks[target] = _STATE.high_load_ticks.get(target, 0) + 1
        else:
            _STATE.high_load_ticks[target] = 0


def _maybe_force_high_load_actions(
    world_state: Dict[str, Any],
    tick: int,
    execute_action_fn: Optional[Callable[[Dict[str, Any], str, Optional[str]], Any]] = None,
    conn: Any = None,
) -> List[Dict[str, Any]]:
    decisions: List[Dict[str, Any]] = []
    for target, count in _STATE.high_load_ticks.items():
        if count < HIGH_LOAD_TICKS:
            continue
        last_tick = _STATE.last_forced_tick.get(target)
        if last_tick is not None and tick - last_tick < HIGH_LOAD_FORCE_COOLDOWN:
            continue

        action = _select_forced_action(target)
        world_state = _execute_action(world_state, action, target, execute_action_fn)
        event_service.append_event(
            tick=tick,
            event_type="action",
            message=f"forced {action} on {target}: sustained load",
            payload={"action": action, "target": target, "forced": True},
            conn=conn,
        )
        decisions.append({"action": action, "target": target, "blocked": False})
        _STATE.last_forced_tick[target] = tick
        _STATE.last_forced_action[target] = action
        _STATE.high_load_ticks[target] = 0
    return decisions


def _select_forced_action(target: str) -> str:
    last_action = _STATE.last_forced_action.get(target)
    if last_action == "reroute":
        return "throttle"
    return "reroute"


def _should_emit_blocked(action: str, target: Optional[str], tick: int) -> bool:
    key = f"{action}:{target or ''}"
    last_tick = _STATE.last_blocked_action.get(key)
    if last_tick is not None and tick - last_tick < BLOCKED_EVENT_COOLDOWN:
        return False
    _STATE.last_blocked_action[key] = tick
    return True
