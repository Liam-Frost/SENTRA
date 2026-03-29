from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.core import controller
from app.services import action_service


@dataclass(frozen=True)
class ActionSpec:
    type: str
    label: str
    capability: str
    availability: str
    risk_level: int
    requires_target: bool


def list_actions(conn: sqlite3.Connection) -> List[ActionSpec]:
    """
    List all actions from database.
    
    Args:
        conn: Database connection
    
    Returns:
        List of ActionSpec objects
    """
    actions_data = action_service.list_actions(conn)
    return [_dict_to_spec(data) for data in actions_data]


def get_action(action_type: str, conn: sqlite3.Connection) -> Optional[ActionSpec]:
    """
    Get a single action from database.
    
    Args:
        action_type: Action ID/type
        conn: Database connection
    
    Returns:
        ActionSpec object or None if not found
    """
    if not isinstance(action_type, str):
        return None
    
    action_data = action_service.get_action(conn, action_type)
    if not action_data:
        return None
    
    return _dict_to_spec(action_data)


def action_types(conn: sqlite3.Connection) -> List[str]:
    """
    Get list of all action IDs.
    
    Args:
        conn: Database connection
    
    Returns:
        List of action IDs
    """
    actions = list_actions(conn)
    return [spec.type for spec in actions]


def _dict_to_spec(data: Dict[str, Any]) -> ActionSpec:
    """Convert action dictionary to ActionSpec."""
    return ActionSpec(
        type=data["id"],
        label=data["label"],
        capability=data["capability"],
        availability=data["availability"],
        risk_level=data["risk_level"],
        requires_target=data["requires_target"],
    )


def is_action_available(action_type: str, run_mode: str, conn: sqlite3.Connection) -> bool:
    """
    Check if action is available for the given run mode.
    
    Args:
        action_type: Action ID/type
        run_mode: Run mode ("simulation" or "probe")
        conn: Database connection
    
    Returns:
        True if action is available, False otherwise
    """
    spec = get_action(action_type, conn)
    if spec is None:
        return False
    if spec.availability != "available":
        return False
    if run_mode == "simulation":
        return spec.capability in {"simulation", "both", "probe"}
    return spec.capability in {"probe", "both", "simulation"}


def evaluate_action(
    action_type: str, world_state: Dict[str, Any], target: Optional[str], conn: sqlite3.Connection
) -> Tuple[bool, str, bool, bool]:
    """
    Returns (allowed, reason, blocking, noop).
    - allowed: action can be applied (or treated as noop)
    - blocking: if False and not allowed, caller can try next action
    - noop: action is effectively a no-op but should be treated as success
    
    Args:
        action_type: Action ID/type
        world_state: Current world state
        target: Target node ID (optional)
        conn: Database connection
    
    Returns:
        Tuple of (allowed, reason, blocking, noop)
    """
    spec = get_action(action_type, conn)
    if spec is None:
        return False, "unknown_action", True, False

    servers = (world_state or {}).get("servers", {})
    server = None
    if spec.requires_target:
        if not target:
            return False, "target_required", True, False
        server = servers.get(target)
        if server is None:
            return False, "unknown_target", True, False

    if spec.requires_target and server is not None:
        status = server.get("status")
        if status not in (None, "running"):
            return False, "server_not_running", False, False

    if action_type == "enableCooling":
        if server and server.get("cooling") is True:
            return True, "cooling_already_enabled", False, True
        return True, "", False, False

    if action_type == "disableCooling":
        if server and server.get("cooling") is False:
            return True, "cooling_already_disabled", False, True
        return True, "", False, False

    if action_type == "restart":
        if server is None:
            return False, "unknown_target", True, False
        if controller.is_restart_safe(server):
            return True, "", False, False
        temp = server.get("temp")
        error_rate = server.get("error_rate")
        return (
            False,
            f"restart_unsafe temp={temp} error_rate={error_rate}",
            True,
            False,
        )

    # reroute/throttle and probe actions always allowed (treated as no-op in sim if needed).
    return True, "", False, False
