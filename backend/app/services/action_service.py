from __future__ import annotations

import json
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

# Default system actions that will be seeded on first init
DEFAULT_ACTIONS = [
    {
        "id": "enableCooling",
        "label": "Enable cooling",
        "category": "cooling",
        "capability": "simulation",
        "availability": "available",
        "risk_level": 0,
        "requires_target": True,
        "description": "Enable cooling system on target node",
        "is_system": True,
    },
    {
        "id": "disableCooling",
        "label": "Disable cooling",
        "category": "cooling",
        "capability": "simulation",
        "availability": "available",
        "risk_level": 0,
        "requires_target": True,
        "description": "Disable cooling system on target node",
        "is_system": True,
    },
    {
        "id": "throttle",
        "label": "Throttle",
        "category": "routing",
        "capability": "both",
        "availability": "available",
        "risk_level": 0,
        "requires_target": False,
        "description": "Throttle traffic to reduce load",
        "is_system": True,
    },
    {
        "id": "reroute",
        "label": "Reroute",
        "category": "routing",
        "capability": "both",
        "availability": "available",
        "risk_level": 1,
        "requires_target": True,
        "description": "Reroute traffic away from target node",
        "is_system": True,
    },
    {
        "id": "restart",
        "label": "Restart node",
        "category": "lifecycle",
        "capability": "simulation",
        "availability": "available",
        "risk_level": 3,
        "requires_target": True,
        "description": "Restart target node (simulation only)",
        "is_system": True,
    },
    {
        "id": "maintenance_toggle",
        "label": "Maintenance on/off",
        "category": "lifecycle",
        "capability": "probe",
        "availability": "available",
        "risk_level": 1,
        "requires_target": True,
        "description": "Toggle maintenance mode on target node",
        "is_system": True,
    },
    {
        "id": "health_check",
        "label": "Health check",
        "category": "diagnostics",
        "capability": "probe",
        "availability": "available",
        "risk_level": 1,
        "requires_target": True,
        "description": "Run health check on target node",
        "is_system": True,
    },
    {
        "id": "diagnostics",
        "label": "Diagnostics",
        "category": "diagnostics",
        "capability": "probe",
        "availability": "available",
        "risk_level": 1,
        "requires_target": True,
        "description": "Run diagnostics on target node",
        "is_system": True,
    },
    {
        "id": "custom",
        "label": "Custom action",
        "category": "custom",
        "capability": "probe",
        "availability": "available",
        "risk_level": 2,
        "requires_target": True,
        "description": "Execute custom action on target node",
        "is_system": True,
    },
    {
        "id": "maintenance_on",
        "label": "Maintenance on",
        "category": "lifecycle",
        "capability": "probe",
        "availability": "future",
        "risk_level": 1,
        "requires_target": True,
        "description": "Enable maintenance mode on target node",
        "is_system": True,
    },
    {
        "id": "maintenance_off",
        "label": "Maintenance off",
        "category": "lifecycle",
        "capability": "probe",
        "availability": "future",
        "risk_level": 1,
        "requires_target": True,
        "description": "Disable maintenance mode on target node",
        "is_system": True,
    },
    {
        "id": "restart_service",
        "label": "Restart service",
        "category": "lifecycle",
        "capability": "probe",
        "availability": "available",
        "risk_level": 2,
        "requires_target": True,
        "description": "Restart specific service on target node",
        "is_system": True,
        "parameters_schema": json.dumps({
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "Name of the service to restart"
                }
            },
            "required": ["service_name"]
        }),
    },
    {
        "id": "restart_host",
        "label": "Restart host",
        "category": "lifecycle",
        "capability": "probe",
        "availability": "available",
        "risk_level": 3,
        "requires_target": True,
        "description": "Restart host machine (high risk)",
        "is_system": True,
    },
    {
        "id": "shutdown_host",
        "label": "Shutdown host",
        "category": "lifecycle",
        "capability": "probe",
        "availability": "available",
        "risk_level": 3,
        "requires_target": True,
        "description": "Shutdown host machine",
        "is_system": True,
    },
    {
        "id": "run_script",
        "label": "Run script",
        "category": "custom",
        "capability": "probe",
        "availability": "available",
        "risk_level": 3,
        "requires_target": True,
        "description": "Run custom script on target node",
        "is_system": True,
        "parameters_schema": json.dumps({
            "type": "object",
            "properties": {
                "script_path": {
                    "type": "string",
                    "description": "Path to script file"
                },
                "timeout": {
                    "type": "number",
                    "default": 60,
                    "description": "Timeout in seconds"
                }
            },
            "required": ["script_path"]
        }),
    },
    {
        "id": "run_command",
        "label": "Run command",
        "category": "custom",
        "capability": "probe",
        "availability": "available",
        "risk_level": 3,
        "requires_target": True,
        "description": "Run shell command on target node",
        "is_system": True,
        "parameters_schema": json.dumps(
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command text"},
                    "timeout": {
                        "type": "number",
                        "default": 60,
                        "description": "Timeout in seconds",
                    },
                },
                "required": ["command"],
            }
        ),
    },
    {
        "id": "deploy_lb_node",
        "label": "Deploy LB node",
        "category": "load_balancer",
        "capability": "probe",
        "availability": "available",
        "risk_level": 2,
        "requires_target": True,
        "description": "Install and configure load balancer on target node",
        "is_system": True,
    },
    {
        "id": "remove_lb_node",
        "label": "Remove LB node",
        "category": "load_balancer",
        "capability": "probe",
        "availability": "available",
        "risk_level": 2,
        "requires_target": True,
        "description": "Uninstall load balancer from target node",
        "is_system": True,
    },
    {
        "id": "template_execution",
        "label": "Template execution",
        "category": "operations",
        "capability": "probe",
        "availability": "available",
        "risk_level": 3,
        "requires_target": True,
        "description": "Execute a multi-step shell command template on target nodes",
        "is_system": True,
    },
]


def list_actions(
    conn: sqlite3.Connection,
    availability: Optional[str] = None,
    capability: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List all actions with optional filters.
    
    Args:
        conn: Database connection
        availability: Filter by availability ("available", "future", "deprecated")
        capability: Filter by capability ("simulation", "probe", "both")
        category: Filter by category
    
    Returns:
        List of action dictionaries
    """
    ensure_default_actions(conn)
    
    query = "SELECT * FROM actions WHERE 1=1"
    params: List[Any] = []
    
    if availability:
        query += " AND availability = ?"
        params.append(availability)
    
    if capability:
        query += " AND capability = ?"
        params.append(capability)
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    query += " ORDER BY is_system DESC, category, label"
    
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    
    return [_row_to_dict(row) for row in rows]


def get_action(conn: sqlite3.Connection, action_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single action by ID.
    
    Args:
        conn: Database connection
        action_id: Action ID
    
    Returns:
        Action dictionary or None if not found
    """
    ensure_default_actions(conn)
    
    cursor = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,))
    row = cursor.fetchone()
    
    if not row:
        return None
    
    return _row_to_dict(row)


def create_action(conn: sqlite3.Connection, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new action.
    
    Args:
        conn: Database connection
        data: Action data dictionary
    
    Returns:
        Created action dictionary
    
    Raises:
        ValueError: If validation fails
    """
    errors = validate_action_data(data, is_create=True)
    if errors:
        raise ValueError("; ".join(errors))
    
    # Check if action with same ID already exists
    existing = get_action(conn, data["id"])
    if existing:
        raise ValueError(f"Action with id '{data['id']}' already exists")
    
    now = int(time.time() * 1000)
    
    action = {
        "id": data["id"],
        "label": data["label"],
        "category": data.get("category"),
        "capability": data["capability"],
        "availability": data["availability"],
        "risk_level": data["risk_level"],
        "requires_target": int(data.get("requires_target", True)),
        "description": data.get("description"),
        "parameters_schema": data.get("parameters_schema"),
        "default_parameters": data.get("default_parameters"),
        "is_system": 0,  # Custom actions are never system actions
        "created_at": now,
        "updated_at": now,
    }
    
    conn.execute(
        """
        INSERT INTO actions (
            id, label, category, capability, availability, risk_level,
            requires_target, description, parameters_schema, default_parameters,
            is_system, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action["id"],
            action["label"],
            action["category"],
            action["capability"],
            action["availability"],
            action["risk_level"],
            action["requires_target"],
            action["description"],
            action["parameters_schema"],
            action["default_parameters"],
            action["is_system"],
            action["created_at"],
            action["updated_at"],
        ),
    )
    conn.commit()
    
    return action


def update_action(
    conn: sqlite3.Connection, action_id: str, data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update an existing action.
    
    Args:
        conn: Database connection
        action_id: Action ID to update
        data: Updated action data
    
    Returns:
        Updated action dictionary
    
    Raises:
        ValueError: If validation fails or action not found
    """
    existing = get_action(conn, action_id)
    if not existing:
        raise ValueError(f"Action '{action_id}' not found")
    
    # System actions can only update label and description
    if existing["is_system"]:
        allowed_fields = {"label", "description"}
        if any(k not in allowed_fields for k in data.keys()):
            raise ValueError(
                "System actions can only update label and description"
            )
    
    errors = validate_action_data(data, is_create=False)
    if errors:
        raise ValueError("; ".join(errors))
    
    now = int(time.time() * 1000)
    
    # Build update query dynamically based on provided fields
    update_fields = []
    params = []
    
    for field in [
        "label",
        "category",
        "capability",
        "availability",
        "risk_level",
        "requires_target",
        "description",
        "parameters_schema",
        "default_parameters",
    ]:
        if field in data:
            update_fields.append(f"{field} = ?")
            value = data[field]
            if field == "requires_target":
                value = int(value)
            params.append(value)
    
    if not update_fields:
        return existing
    
    update_fields.append("updated_at = ?")
    params.append(now)
    params.append(action_id)
    
    query = f"UPDATE actions SET {', '.join(update_fields)} WHERE id = ?"
    conn.execute(query, params)
    conn.commit()
    
    return get_action(conn, action_id) or existing


def delete_action(conn: sqlite3.Connection, action_id: str) -> bool:
    """
    Delete an action.
    
    Args:
        conn: Database connection
        action_id: Action ID to delete
    
    Returns:
        True if deleted, False if not found
    
    Raises:
        ValueError: If action is a system action or is referenced by policies/operations
    """
    action = get_action(conn, action_id)
    if not action:
        return False
    
    if action["is_system"]:
        raise ValueError("Cannot delete system action")
    
    # Check if action is referenced
    can_delete, reason = can_delete_action(conn, action_id)
    if not can_delete:
        raise ValueError(reason)
    
    conn.execute("DELETE FROM actions WHERE id = ?", (action_id,))
    conn.commit()
    
    return True


def get_action_references(
    conn: sqlite3.Connection, action_id: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all references to an action (policies and operations that use it).
    
    Args:
        conn: Database connection
        action_id: Action ID
    
    Returns:
        Dictionary with "policies" and "operations" keys containing references
    """
    references: Dict[str, List[Dict[str, Any]]] = {"policies": [], "operations": []}
    
    # Check policies
    cursor = conn.execute("SELECT id, name, data FROM policies")
    for row in cursor.fetchall():
        try:
            policy_data = json.loads(row["data"])
            actions = policy_data.get("actions", [])
            if any(a.get("type") == action_id for a in actions):
                references["policies"].append({
                    "id": row["id"],
                    "name": row["name"],
                })
        except (json.JSONDecodeError, KeyError):
            continue
    
    # Check operations
    cursor = conn.execute(
        """
        SELECT id, action_type, status, created_at
        FROM operations
        WHERE action_type = ? AND status IN ('queued', 'pending', 'approved')
        """,
        (action_id,),
    )
    for row in cursor.fetchall():
        references["operations"].append({
            "id": row["id"],
            "action_type": row["action_type"],
            "status": row["status"],
            "created_at": row["created_at"],
        })
    
    return references


def can_delete_action(conn: sqlite3.Connection, action_id: str) -> Tuple[bool, str]:
    """
    Check if an action can be deleted.
    
    Args:
        conn: Database connection
        action_id: Action ID
    
    Returns:
        Tuple of (can_delete, reason)
    """
    action = get_action(conn, action_id)
    if not action:
        return False, "Action not found"
    
    if action["is_system"]:
        return False, "Cannot delete system action"
    
    references = get_action_references(conn, action_id)
    
    policy_count = len(references["policies"])
    operation_count = len(references["operations"])
    
    if policy_count > 0 or operation_count > 0:
        parts = []
        if policy_count > 0:
            parts.append(f"{policy_count} {'policy' if policy_count == 1 else 'policies'}")
        if operation_count > 0:
            parts.append(f"{operation_count} pending {'operation' if operation_count == 1 else 'operations'}")
        reason = f"Cannot delete: used by {' and '.join(parts)}"
        return False, reason
    
    return True, ""


def validate_action_data(data: Dict[str, Any], is_create: bool = False) -> List[str]:
    """
    Validate action data.
    
    Args:
        data: Action data to validate
        is_create: Whether this is a create operation (validates ID)
    
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    if is_create:
        if "id" not in data or not data["id"]:
            errors.append("id is required")
        elif not re.match(r"^[a-zA-Z0-9_]{1,50}$", data["id"]):
            errors.append("id must be 1-50 alphanumeric characters or underscores")
    
    if "label" in data and not data["label"].strip():
        errors.append("label cannot be empty")
    
    if "capability" in data and data["capability"] not in ["simulation", "probe", "both"]:
        errors.append("capability must be 'simulation', 'probe', or 'both'")
    
    if "availability" in data and data["availability"] not in [
        "available",
        "future",
        "deprecated",
    ]:
        errors.append("availability must be 'available', 'future', or 'deprecated'")
    
    if "risk_level" in data:
        try:
            risk = int(data["risk_level"])
            if risk < 0 or risk > 3:
                errors.append("risk_level must be 0-3")
        except (ValueError, TypeError):
            errors.append("risk_level must be an integer")
    
    # Validate JSON schemas if provided
    if "parameters_schema" in data and data["parameters_schema"]:
        try:
            json.loads(data["parameters_schema"])
        except json.JSONDecodeError:
            errors.append("parameters_schema must be valid JSON")
    
    if "default_parameters" in data and data["default_parameters"]:
        try:
            json.loads(data["default_parameters"])
        except json.JSONDecodeError:
            errors.append("default_parameters must be valid JSON")
    
    return errors


def validate_parameters(
    action: Dict[str, Any], parameters: Dict[str, Any]
) -> List[str]:
    """
    Validate parameters against action's parameters_schema.
    
    Args:
        action: Action dictionary
        parameters: Parameters to validate
    
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    if not action.get("parameters_schema"):
        # No schema defined, accept any parameters
        return errors
    
    try:
        schema = json.loads(action["parameters_schema"])
    except json.JSONDecodeError:
        return ["Invalid parameters_schema in action"]
    
    # Basic JSON schema validation (simplified)
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # Check required fields
        for field in required:
            if field not in parameters:
                errors.append(f"Required parameter '{field}' is missing")
        
        # Check parameter types
        for key, value in parameters.items():
            if key in properties:
                prop = properties[key]
                expected_type = prop.get("type")
                
                if expected_type == "string" and not isinstance(value, str):
                    errors.append(f"Parameter '{key}' must be a string")
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Parameter '{key}' must be a number")
                elif expected_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Parameter '{key}' must be a boolean")
    
    return errors


def ensure_default_actions(conn: sqlite3.Connection) -> None:
    """
    Seed default system actions if actions table is empty.
    
    Args:
        conn: Database connection
    """
    cursor = conn.execute("SELECT COUNT(*) as count FROM actions")
    row = cursor.fetchone()
    
    if row["count"] > 0:
        return
    
    now = int(time.time() * 1000)
    
    for action_data in DEFAULT_ACTIONS:
        conn.execute(
            """
            INSERT INTO actions (
                id, label, category, capability, availability, risk_level,
                requires_target, description, parameters_schema, default_parameters,
                is_system, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action_data["id"],
                action_data["label"],
                action_data.get("category"),
                action_data["capability"],
                action_data["availability"],
                action_data["risk_level"],
                int(action_data["requires_target"]),
                action_data.get("description"),
                action_data.get("parameters_schema"),
                action_data.get("default_parameters"),
                1,  # is_system
                now,
                now,
            ),
        )
    
    conn.commit()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a SQLite row to a dictionary."""
    return {
        "id": row["id"],
        "label": row["label"],
        "category": row["category"],
        "capability": row["capability"],
        "availability": row["availability"],
        "risk_level": row["risk_level"],
        "requires_target": bool(row["requires_target"]),
        "description": row["description"],
        "parameters_schema": row["parameters_schema"],
        "default_parameters": row["default_parameters"],
        "is_system": bool(row["is_system"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
