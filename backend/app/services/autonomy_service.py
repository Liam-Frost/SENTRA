from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from app.core import controller
from app.core.ai import ai_client
from app.services import event_service

WAIT_TICKS = 5


@dataclass
class TargetState:
    last_action: Optional[str] = None
    last_action_tick: Optional[int] = None


@dataclass
class AutonomyState:
    enabled: bool = False
    targets: Dict[str, TargetState] = field(default_factory=dict)
    last_tick_processed: Optional[int] = None


_STATE = AutonomyState()
_STATE_LOCK = threading.RLock()


def set_autonomy_enabled(enabled: bool, tick: Optional[int] = None, conn: Any = None) -> bool:
    with _STATE_LOCK:
        _STATE.enabled = bool(enabled)
        if not _STATE.enabled:
            _STATE.targets.clear()
            _STATE.last_tick_processed = None
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

        incidents = controller.detect_incidents(world_state)

        for incident in incidents:
            event_service.append_event(
                tick=tick,
                event_type="incident",
                message=incident["message"],
                payload={
                    "target": incident["target"],
                    "metric": incident["metric"],
                    "value": incident["value"],
                    "threshold": incident["threshold"],
                },
                conn=conn,
            )

        active_targets = {incident["target"] for incident in incidents}
        _clear_inactive_targets(active_targets)

        decisions: List[Dict[str, Any]] = []
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
                event_service.append_event(
                    tick=tick,
                    event_type="action",
                    message=f"blocked {decision['action']} on {target}: {decision['reason']}",
                    payload={"action": decision["action"], "target": target},
                    conn=conn,
                )
                continue

            event_service.append_event(
                tick=tick,
                event_type="action",
                message=f"decide {decision['action']} on {target}",
                payload={"action": decision["action"], "target": target},
                conn=conn,
            )

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

        if incidents:
            explainer = ai_explainer_fn or ai_client.explain_incidents
            ai_payload = explainer(world_state, incidents, decisions)
            event_service.append_event(
                tick=tick,
                event_type="ai",
                message="ai explanation",
                payload=ai_payload,
                conn=conn,
            )

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
        return world_state
    if action == "disableCooling":
        server["cooling"] = False
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
