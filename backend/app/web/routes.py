from __future__ import annotations

import time

from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from app.persistence import db
from app.services import (
    action_service,
    autonomy_service,
    event_service,
    infrastructure_service,
    lb_policy_service,
    operation_service,
    operation_templates_service,
    policy_engine,
    policy_service,
    runtime_config,
    tick_service,
)

bp = Blueprint("api", __name__, url_prefix="/api")

#if teammate B upload their function, update any about tick_service helper function here
@bp.get("/capabilities")
def get_capabilities():
    sim_enabled = runtime_config.is_simulation_enabled()
    return jsonify(
        {
            "simulation_enabled": sim_enabled,
            "database_backend": db.get_database_backend(),
            "run_mode": operation_service.get_run_mode(),
            "features": {
                "dashboard": True,
                "fleet": True,
                "operations": True,
                "actions": True,
                "policies": True,
                "projects": True,
                "load_balancers": True,
                "simulation_controls": sim_enabled,
            },
        }
    )


@bp.get("/state")
def get_state():
    if runtime_config.is_simulation_enabled():
        return jsonify(tick_service.get_state())

    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(infrastructure_service.get_world_state(conn))
    finally:
        conn.close()


@bp.post("/tick")
def post_tick():
    blocked = _simulation_guard()
    if blocked:
        return blocked
    body = request.get_json(silent=True) or {}
    steps = body.get("steps", 1)
    if not _is_positive_int(steps):
        return _bad_request("steps must be a positive integer")
    return jsonify(tick_service.advance(int(steps)))


@bp.post("/fault")
def post_fault():
    blocked = _simulation_guard()
    if blocked:
        return blocked
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
    blocked = _simulation_guard()
    if blocked:
        return blocked
    body = request.get_json(silent=True) or {}
    if "enabled" not in body or not isinstance(body.get("enabled"), bool):
        return _bad_request("enabled must be boolean")
    enabled = autonomy_service.set_autonomy_enabled(body["enabled"], tick=tick_service.get_tick())
    return jsonify({"enabled": enabled})


@bp.post("/reset")
def post_reset():
    blocked = _simulation_guard()
    if blocked:
        return blocked
    body = request.get_json(silent=True) or {}
    reset_events = body.get("reset_events", True)
    if not isinstance(reset_events, bool):
        return _bad_request("reset_events must be boolean")
    return jsonify(tick_service.reset(reset_events=reset_events))


@bp.get("/realtime")
def get_realtime():
    blocked = _simulation_guard()
    if blocked:
        return blocked
    return jsonify(tick_service.get_realtime_state())


@bp.post("/realtime")
def post_realtime():
    blocked = _simulation_guard()
    if blocked:
        return blocked
    body = request.get_json(silent=True) or {}
    if "enabled" not in body or not isinstance(body.get("enabled"), bool):
        return _bad_request("enabled must be boolean")
    hz = body.get("hz")
    if hz is not None and not isinstance(hz, (int, float)):
        return _bad_request("hz must be a number")
    try:
        return jsonify(tick_service.set_realtime(body["enabled"], hz=hz))
    except ValueError as exc:
        return _bad_request(str(exc))


@bp.get("/actions")
def get_actions():
    availability = request.args.get("availability")
    capability = request.args.get("capability")
    category = request.args.get("category")

    conn = db.connect()
    try:
        db.init_db(conn)
        actions = action_service.list_actions(
            conn,
            availability=availability,
            capability=capability,
            category=category,
        )
        return jsonify({"actions": actions})
    finally:
        conn.close()


@bp.get("/actions/<action_id>")
def get_action_by_id(action_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        action = action_service.get_action(conn, action_id)
        if not action:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "action not found"}}), 404
        return jsonify({"action": action})
    finally:
        conn.close()


@bp.post("/actions")
def post_action():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            created = action_service.create_action(conn, body)
        except ValueError as exc:
            return _bad_request(str(exc))
        # Normalize response using DB-backed representation.
        action = action_service.get_action(conn, str(created.get("id") or ""))
        return jsonify({"action": action or created})
    finally:
        conn.close()


@bp.put("/actions/<action_id>")
def put_action(action_id: str):
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            updated = action_service.update_action(conn, action_id, body)
        except ValueError as exc:
            return _bad_request(str(exc))
        return jsonify({"action": updated})
    finally:
        conn.close()


@bp.delete("/actions/<action_id>")
def delete_action(action_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            deleted = action_service.delete_action(conn, action_id)
        except ValueError as exc:
            return _bad_request(str(exc))
        if not deleted:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "action not found"}}), 404
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.post("/actions/execute")
def post_execute_actions():
    body = request.get_json(silent=True) or {}
    actions = body.get("actions")
    targets = body.get("targets")
    initiator = body.get("initiator")

    if not isinstance(actions, list) or not actions:
        return _bad_request("actions must be a non-empty list")
    if targets is not None and not isinstance(targets, list):
        return _bad_request("targets must be a list")
    if initiator is not None and not isinstance(initiator, str):
        return _bad_request("initiator must be a string")

    conn = db.connect()
    try:
        db.init_db(conn)
        op_ids: List[str] = []
        for action_type in actions:
            if not isinstance(action_type, str) or not action_type.strip():
                return _bad_request("actions must contain only strings")
            operation = operation_service.create_operation(
                action_type=str(action_type),
                targets=[str(t) for t in (targets or []) if isinstance(t, str) and t.strip()],
                initiator=str(initiator or "bulk"),
                conn=conn,
            )
            op_id = operation.get("id")
            if isinstance(op_id, str):
                op_ids.append(op_id)
        return jsonify({"operations": op_ids})
    except ValueError as exc:
        return _bad_request(str(exc))
    finally:
        conn.close()


@bp.get("/actions/<action_id>/references")
def get_action_references(action_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        refs = action_service.get_action_references(conn, action_id)
        return jsonify(refs)
    finally:
        conn.close()


@bp.get("/operation-templates")
def get_operation_templates():
    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(operation_templates_service.list_templates(conn))
    finally:
        conn.close()


@bp.post("/operation-templates")
def post_operation_templates():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            template = operation_templates_service.create_template(body, conn)
        except ValueError as exc:
            return _bad_request(str(exc))
        event_service.append_event(
            tick=int(time.time()),
            event_type="operation",
            message=f"operation template created: {template.get('name')}",
            payload={"template_id": template.get("id"), "name": template.get("name")},
            conn=conn,
        )
        return jsonify({"template": template})
    finally:
        conn.close()


@bp.get("/operation-templates/<template_id>")
def get_operation_template_by_id(template_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        template = operation_templates_service.get_template(template_id, conn)
        if not template:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "template not found"}}), 404
        return jsonify({"template": template})
    finally:
        conn.close()


@bp.put("/operation-templates/<template_id>")
def put_operation_template(template_id: str):
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            template = operation_templates_service.update_template(template_id, body, conn)
        except ValueError as exc:
            message = str(exc)
            if message == "template not found":
                return jsonify({"error": {"code": "NOT_FOUND", "message": message}}), 404
            return _bad_request(message)
        event_service.append_event(
            tick=int(time.time()),
            event_type="operation",
            message=f"operation template updated: {template.get('name')}",
            payload={"template_id": template.get("id"), "name": template.get("name")},
            conn=conn,
        )
        return jsonify({"template": template})
    finally:
        conn.close()


@bp.delete("/operation-templates/<template_id>")
def delete_operation_template(template_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        ok = operation_templates_service.delete_template(template_id, conn)
        if not ok:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "template not found"}}), 404
        event_service.append_event(
            tick=int(time.time()),
            event_type="operation",
            message=f"operation template deleted: {template_id}",
            payload={"template_id": template_id},
            conn=conn,
        )
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.post("/operation-templates/<template_id>/execute")
def post_operation_template_execute(template_id: str):
    body = request.get_json(silent=True) or {}
    targets = body.get("targets")
    initiator = body.get("initiator")
    if not isinstance(targets, list):
        return _bad_request("targets must be a list")
    if initiator is not None and not isinstance(initiator, str):
        return _bad_request("initiator must be a string")
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            execution = operation_templates_service.execute_template(
                template_id,
                [str(item) for item in targets if isinstance(item, str) and item.strip()],
                initiator=str(initiator or "manual"),
                source="manual",
                conn=conn,
            )
        except ValueError as exc:
            message = str(exc)
            if message == "template not found":
                return jsonify({"error": {"code": "NOT_FOUND", "message": message}}), 404
            return _bad_request(message)
        event_service.append_event(
            tick=int(time.time()),
            event_type="operation",
            message=f"template executed: {template_id}",
            payload={"template_id": template_id, "execution_id": execution.get("id")},
            conn=conn,
        )
        return jsonify({"execution": execution})
    finally:
        conn.close()


@bp.get("/operation-executions")
def get_operation_executions():
    template_id = request.args.get("template_id")
    source = request.args.get("source")
    limit_raw = request.args.get("limit")
    limit = _parse_optional_int(limit_raw) or 50
    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(
            operation_templates_service.list_executions(
                conn,
                template_id=template_id,
                source=source,
                limit=limit,
            )
        )
    finally:
        conn.close()


@bp.get("/operation-executions/<execution_id>")
def get_operation_execution_by_id(execution_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        execution = operation_templates_service.get_execution(execution_id, conn)
        if not execution:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "execution not found"}}), 404
        return jsonify(execution)
    finally:
        conn.close()


@bp.get("/lb-policies")
def get_lb_policies():
    project_id = request.args.get("project_id")
    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(lb_policy_service.list_policies(conn, project_id=project_id))
    finally:
        conn.close()


@bp.post("/lb-policies")
def post_lb_policies():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            policy = lb_policy_service.create_policy(body, conn)
        except ValueError as exc:
            return _bad_request(str(exc))
        event_service.append_event(
            tick=int(time.time()),
            event_type="load_balancer",
            message=f"LB policy created: {policy.get('name')}",
            payload={"lb_policy_id": policy.get("id"), "project_id": policy.get("projectId")},
            conn=conn,
        )
        return jsonify({"policy": policy})
    finally:
        conn.close()


@bp.get("/lb-policies/<policy_id>")
def get_lb_policy_by_id(policy_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        policy = lb_policy_service.get_policy(policy_id, conn)
        if not policy:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "policy not found"}}), 404
        return jsonify({"policy": policy})
    finally:
        conn.close()


@bp.put("/lb-policies/<policy_id>")
def put_lb_policy(policy_id: str):
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            policy = lb_policy_service.update_policy(policy_id, body, conn)
        except ValueError as exc:
            message = str(exc)
            if message == "policy not found":
                return jsonify({"error": {"code": "NOT_FOUND", "message": message}}), 404
            return _bad_request(message)
        event_service.append_event(
            tick=int(time.time()),
            event_type="load_balancer",
            message=f"LB policy updated: {policy.get('name')}",
            payload={"lb_policy_id": policy.get("id"), "project_id": policy.get("projectId")},
            conn=conn,
        )
        return jsonify({"policy": policy})
    finally:
        conn.close()


@bp.delete("/lb-policies/<policy_id>")
def delete_lb_policy(policy_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        ok = lb_policy_service.delete_policy(policy_id, conn)
        if not ok:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "policy not found"}}), 404
        event_service.append_event(
            tick=int(time.time()),
            event_type="load_balancer",
            message=f"LB policy deleted: {policy_id}",
            payload={"lb_policy_id": policy_id},
            conn=conn,
        )
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.post("/lb-policies/<policy_id>/apply")
def post_lb_policy_apply(policy_id: str):
    body = request.get_json(silent=True) or {}
    initiator = body.get("initiator")
    if initiator is not None and not isinstance(initiator, str):
        return _bad_request("initiator must be a string")
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            result = lb_policy_service.apply_policy(
                policy_id,
                initiator=str(initiator or "policy"),
                conn=conn,
            )
        except ValueError as exc:
            message = str(exc)
            if message == "policy not found":
                return jsonify({"error": {"code": "NOT_FOUND", "message": message}}), 404
            return _bad_request(message)
        event_service.append_event(
            tick=int(time.time()),
            event_type="load_balancer",
            message=f"LB policy applied: {policy_id}",
            payload={"lb_policy_id": policy_id, "execution_id": result.get("execution", {}).get("id")},
            conn=conn,
        )
        return jsonify(result)
    finally:
        conn.close()


@bp.get("/policies")
def get_policies():
    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(policy_service.list_policies(conn=conn))
    finally:
        conn.close()


@bp.post("/policies")
def post_policies():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            policy = policy_service.create_policy(body, conn=conn)
        except ValueError as exc:
            return _bad_request(str(exc))
        return jsonify({"policy": policy})
    finally:
        conn.close()


@bp.get("/policies/<policy_id>")
def get_policy_by_id(policy_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        policy = policy_service.get_policy(policy_id, conn=conn)
        if not policy:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "policy not found"}}), 404
        versions = policy_service.list_policy_versions(policy_id, conn=conn)
        return jsonify({"policy": policy, "versions": versions})
    finally:
        conn.close()


@bp.put("/policies/<policy_id>")
def put_policy(policy_id: str):
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            policy = policy_service.update_policy(policy_id, body, conn=conn)
        except KeyError:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "policy not found"}}), 404
        except ValueError as exc:
            return _bad_request(str(exc))
        return jsonify({"policy": policy})
    finally:
        conn.close()


@bp.delete("/policies/<policy_id>")
def delete_policy(policy_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        ok = policy_service.delete_policy(policy_id, conn=conn)
        if not ok:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "policy not found"}}), 404
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.post("/policies/validate")
def post_policy_validate():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        errors = policy_service.validate_policy(body, conn=conn)
        return jsonify({"errors": errors})
    finally:
        conn.close()


@bp.post("/policies/<policy_id>/run")
def post_policy_run(policy_id: str):
    body = request.get_json(silent=True) or {}
    force = bool(body.get("force", False))
    initiator = body.get("initiator")
    if initiator is not None and not isinstance(initiator, str):
        return _bad_request("initiator must be a string")

    conn = db.connect()
    try:
        db.init_db(conn)
        world_state = (
            tick_service.get_state()
            if runtime_config.is_simulation_enabled()
            else infrastructure_service.get_world_state(conn)
        )
        policy = policy_service.get_policy(policy_id, conn=conn)
        if not policy:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "policy not found"}}), 404
        result = policy_engine.run_policy(
            policy,
            world_state,
            conn=conn,
            force=force,
            initiator=str(initiator or "manual"),
        )
        return jsonify(result)
    finally:
        conn.close()


@bp.get("/operations")
def get_operations():
    status = request.args.get("status")
    limit_raw = request.args.get("limit")
    limit = _parse_optional_int(limit_raw)
    if limit_raw is not None:
        if limit is None or limit <= 0:
            return _bad_request("limit must be a positive integer")

    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(operation_service.list_operations(status=status, limit=limit, conn=conn))
    finally:
        conn.close()


@bp.post("/operations")
def post_operations():
    body = request.get_json(silent=True) or {}
    action = body.get("action") if "action" in body else body.get("actionType")
    targets = body.get("targets")
    parameters = body.get("parameters")
    initiator = body.get("initiator")
    approval_state = body.get("approvalState")
    mode = body.get("mode")

    if not isinstance(action, str) or not action.strip():
        return _bad_request("action is required")
    if targets is not None and not isinstance(targets, list):
        return _bad_request("targets must be a list")
    if parameters is not None and not isinstance(parameters, dict):
        return _bad_request("parameters must be an object")
    if initiator is not None and not isinstance(initiator, str):
        return _bad_request("initiator must be a string")
    if approval_state is not None and not isinstance(approval_state, str):
        return _bad_request("approvalState must be a string")
    if mode is not None and not isinstance(mode, str):
        return _bad_request("mode must be a string")

    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            op = operation_service.create_operation(
                action_type=str(action),
                targets=[str(t) for t in (targets or []) if isinstance(t, str) and t.strip()],
                parameters=parameters,
                initiator=str(initiator or "manual"),
                approval_state=str(approval_state or "none"),
                mode=str(mode) if mode is not None else None,
                conn=conn,
            )
        except ValueError as exc:
            return _bad_request(str(exc))
        return jsonify({"operation": op})
    finally:
        conn.close()


@bp.get("/operations/<operation_id>")
def get_operation_by_id(operation_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        result = operation_service.get_operation(operation_id, conn=conn)
        if not result:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "operation not found"}}), 404
        return jsonify(result)
    finally:
        conn.close()


@bp.delete("/operations/<operation_id>")
def delete_operation(operation_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        ok = operation_service.delete_operation(operation_id, conn=conn)
        if not ok:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "operation not found"}}), 404
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.post("/operations/<operation_id>/cancel")
def post_cancel_operation(operation_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        ok = operation_service.cancel_operation(operation_id, conn=conn)
        if not ok:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "operation not found"}}), 404
        event_service.append_event(
            tick=int(time.time()),
            event_type="operation",
            message=f"operation cancelled: {operation_id}",
            payload={"operation_id": operation_id, "status": "cancelled"},
            conn=conn,
        )
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.post("/operations/<operation_id>/retry")
def post_retry_operation(operation_id: str):
    body = request.get_json(silent=True) or {}
    initiator = body.get("initiator")
    if initiator is not None and not isinstance(initiator, str):
        return _bad_request("initiator must be a string")
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            operation = operation_service.retry_operation(
                operation_id,
                initiator=str(initiator or "retry"),
                conn=conn,
            )
        except ValueError as exc:
            return _bad_request(str(exc))
        event_service.append_event(
            tick=int(time.time()),
            event_type="operation",
            message=f"operation retried: {operation_id}",
            payload={"source_operation_id": operation_id, "new_operation_id": operation.get("id")},
            conn=conn,
        )
        return jsonify({"operation": operation})
    finally:
        conn.close()


@bp.get("/operations/<operation_id>/logs")
def get_operation_logs(operation_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(operation_service.list_operation_logs(operation_id, conn=conn))
    finally:
        conn.close()


@bp.get("/dashboard")
def get_dashboard():
    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(infrastructure_service.get_dashboard(conn))
    finally:
        conn.close()


@bp.get("/nodes")
def get_nodes():
    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(infrastructure_service.list_nodes(conn))
    finally:
        conn.close()


@bp.post("/nodes")
def post_nodes():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        node = infrastructure_service.create_or_update_node(body, conn=conn)
        event_service.append_event(
            tick=int(time.time()),
            event_type="node",
            message=f"node upserted: {node.get('id')}",
            payload={"node_id": node.get("id"), "status": node.get("status")},
            conn=conn,
        )
        return jsonify({"node": node})
    finally:
        conn.close()


@bp.get("/nodes/<node_id>")
def get_node_by_id(node_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        node = infrastructure_service.get_node(node_id, conn=conn)
        if not node:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "node not found"}}), 404
        return jsonify({"node": node})
    finally:
        conn.close()


@bp.post("/agents/register")
def post_agent_register():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            result = infrastructure_service.register_agent(body, conn=conn)
        except ValueError as exc:
            return _bad_request(str(exc))
        event_service.append_event(
            tick=int(time.time()),
            event_type="agent",
            message=f"agent registered: {result.get('agentId')}",
            payload={"agent_id": result.get("agentId"), "node_id": result.get("nodeId")},
            conn=conn,
        )
        return jsonify(result)
    finally:
        conn.close()


@bp.post("/agents/heartbeat")
def post_agent_heartbeat():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            result = infrastructure_service.post_heartbeat(body, conn=conn)
        except ValueError as exc:
            return _bad_request(str(exc))
        event_service.append_event(
            tick=int(time.time()),
            event_type="agent",
            message=f"heartbeat: {body.get('agent_id') or body.get('agentId')}",
            payload={
                "agent_id": body.get("agent_id") or body.get("agentId"),
                "node_id": result.get("nodeId"),
                "status": body.get("status") or "online",
            },
            conn=conn,
        )
        return jsonify(result)
    finally:
        conn.close()


@bp.post("/agents/metrics")
def post_agent_metrics():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            result = infrastructure_service.post_metrics(body, conn=conn)
        except ValueError as exc:
            return _bad_request(str(exc))
        metrics = body.get("metrics") if isinstance(body.get("metrics"), dict) else body
        temp = metrics.get("temp")
        error_rate = metrics.get("error_rate") if "error_rate" in metrics else metrics.get("errorRate")
        health = metrics.get("health")
        load = metrics.get("cpu") if "cpu" in metrics else metrics.get("load")
        try:
            temp_val = float(temp if temp is not None else 0.0)
            err_val = float(error_rate if error_rate is not None else 0.0)
            health_val = float(health if health is not None else 100.0)
            load_val = float(load if load is not None else 0.0)
        except (TypeError, ValueError):
            temp_val = 0.0
            err_val = 0.0
            health_val = 100.0
            load_val = 0.0

        if temp_val > 80.0:
            event_service.append_event(
                tick=int(time.time()),
                event_type="incident",
                message=f"temp > 80 on {result.get('nodeId')}",
                payload={
                    "target": result.get("nodeId"),
                    "metric": "temp",
                    "value": temp_val,
                    "threshold": 80,
                    "status": "start",
                },
                conn=conn,
            )
        if err_val > 5.0:
            event_service.append_event(
                tick=int(time.time()),
                event_type="incident",
                message=f"error_rate > 5 on {result.get('nodeId')}",
                payload={
                    "target": result.get("nodeId"),
                    "metric": "error_rate",
                    "value": err_val,
                    "threshold": 5,
                    "status": "start",
                },
                conn=conn,
            )
        if health_val < 60.0:
            event_service.append_event(
                tick=int(time.time()),
                event_type="incident",
                message=f"health < 60 on {result.get('nodeId')}",
                payload={
                    "target": result.get("nodeId"),
                    "metric": "health",
                    "value": health_val,
                    "threshold": 60,
                    "status": "start",
                },
                conn=conn,
            )
        if load_val > 85.0:
            event_service.append_event(
                tick=int(time.time()),
                event_type="incident",
                message=f"load > 85 on {result.get('nodeId')}",
                payload={
                    "target": result.get("nodeId"),
                    "metric": "load",
                    "value": load_val,
                    "threshold": 85,
                    "status": "start",
                },
                conn=conn,
            )
        return jsonify(result)
    finally:
        conn.close()


@bp.get("/agents/commands/next")
def get_agent_next_command():
    agent_id = request.args.get("agent_id") or request.args.get("agentId")
    if not isinstance(agent_id, str) or not agent_id.strip():
        return _bad_request("agent_id is required")

    conn = db.connect()
    try:
        db.init_db(conn)
        agent = infrastructure_service.get_agent(agent_id, conn=conn)
        if not agent:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "agent not found"}}), 404
        command = operation_service.claim_next_run_for_node(str(agent.get("nodeId") or ""), conn=conn)
        return jsonify({"command": command})
    finally:
        conn.close()


@bp.post("/agents/commands/<int:run_id>/logs")
def post_agent_command_log(run_id: int):
    body = request.get_json(silent=True) or {}
    stream = body.get("stream")
    message = body.get("message")
    ts = body.get("ts")
    if not isinstance(message, str) or not message.strip():
        return _bad_request("message is required")
    if stream is not None and not isinstance(stream, str):
        return _bad_request("stream must be a string")

    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            log = operation_service.append_run_log(
                run_id=int(run_id),
                stream=str(stream or "system"),
                message=message,
                ts=int(ts) if isinstance(ts, int) else None,
                conn=conn,
            )
        except ValueError as exc:
            return _bad_request(str(exc))
        return jsonify({"log": log})
    finally:
        conn.close()


@bp.post("/agents/commands/<int:run_id>/result")
def post_agent_command_result(run_id: int):
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if not isinstance(status, str):
        return _bad_request("status is required")
    output = body.get("output")
    if output is not None and not isinstance(output, str):
        return _bad_request("output must be a string")
    exit_code = body.get("exit_code")
    if exit_code is not None and not isinstance(exit_code, int):
        return _bad_request("exit_code must be an integer")

    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            result = operation_service.complete_run(
                int(run_id),
                status=status,
                output=output,
                exit_code=exit_code,
                conn=conn,
            )
        except ValueError as exc:
            return _bad_request(str(exc))
        event_service.append_event(
            tick=int(time.time()),
            event_type="operation",
            message=f"run {run_id} {result.get('status')}",
            payload={
                "operation_id": result.get("operationId"),
                "run_id": run_id,
                "status": result.get("status"),
                "node_id": result.get("nodeId"),
            },
            conn=conn,
        )
        return jsonify(result)
    finally:
        conn.close()


@bp.get("/projects")
def get_projects():
    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(infrastructure_service.list_projects(conn))
    finally:
        conn.close()


@bp.post("/projects")
def post_projects():
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            project = infrastructure_service.create_project(body, conn)
        except ValueError as exc:
            return _bad_request(str(exc))
        event_service.append_event(
            tick=int(time.time()),
            event_type="project",
            message=f"project created: {project.get('name')}",
            payload={"project_id": project.get("id"), "name": project.get("name")},
            conn=conn,
        )
        return jsonify({"project": project})
    finally:
        conn.close()


@bp.put("/projects/<project_id>")
def put_project(project_id: str):
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            project = infrastructure_service.update_project(project_id, body, conn)
        except ValueError as exc:
            message = str(exc)
            if message == "project not found":
                return jsonify({"error": {"code": "NOT_FOUND", "message": message}}), 404
            return _bad_request(message)
        event_service.append_event(
            tick=int(time.time()),
            event_type="project",
            message=f"project updated: {project.get('name')}",
            payload={"project_id": project.get("id"), "name": project.get("name")},
            conn=conn,
        )
        return jsonify({"project": project})
    finally:
        conn.close()


@bp.delete("/projects/<project_id>")
def delete_project(project_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            ok = infrastructure_service.delete_project(project_id, conn)
        except ValueError as exc:
            return _bad_request(str(exc))
        if not ok:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "project not found"}}), 404
        event_service.append_event(
            tick=int(time.time()),
            event_type="project",
            message=f"project deleted: {project_id}",
            payload={"project_id": project_id},
            conn=conn,
        )
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.get("/load-balancers")
def get_load_balancers():
    project_id = request.args.get("project_id")
    node_id = request.args.get("node_id")
    conn = db.connect()
    try:
        db.init_db(conn)
        return jsonify(
            infrastructure_service.list_load_balancers(
                conn,
                project_id=project_id,
                node_id=node_id,
            )
        )
    finally:
        conn.close()


@bp.post("/load-balancers")
def post_load_balancers():
    body = request.get_json(silent=True) or {}
    node_ids = body.get("nodeIds") if isinstance(body.get("nodeIds"), list) else None
    conn = db.connect()
    try:
        db.init_db(conn)
        targets = [str(node_id) for node_id in (node_ids or [body.get("nodeId")]) if isinstance(node_id, str) and node_id.strip()]
        if not targets:
            return _bad_request("nodeId or nodeIds is required")

        created: List[Dict[str, Any]] = []
        operations: List[Dict[str, Any]] = []
        for target in targets:
            lb_payload = dict(body)
            lb_payload["nodeId"] = target
            try:
                lb = infrastructure_service.create_load_balancer(lb_payload, conn)
            except ValueError as exc:
                return _bad_request(str(exc))

            deploy_operation = operation_service.create_operation(
                action_type="deploy_lb_node",
                targets=[str(lb.get("nodeId") or "")],
                parameters={
                    "load_balancer_id": lb.get("id"),
                    "project_id": lb.get("projectId"),
                    "type": lb.get("type"),
                    "listen_port": lb.get("listenPort"),
                },
                initiator="load_balancer",
                conn=conn,
            )
            event_service.append_event(
                tick=int(time.time()),
                event_type="load_balancer",
                message=f"load balancer deployed: {lb.get('id')}",
                payload={
                    "load_balancer_id": lb.get("id"),
                    "project_id": lb.get("projectId"),
                    "node_id": lb.get("nodeId"),
                },
                conn=conn,
            )
            created.append(lb)
            operations.append(deploy_operation)

        if node_ids is not None:
            return jsonify({"loadBalancers": created, "operations": operations})
        return jsonify({"loadBalancer": created[0], "operation": operations[0]})
    finally:
        conn.close()


@bp.delete("/load-balancers/<lb_id>")
def delete_load_balancers(lb_id: str):
    conn = db.connect()
    try:
        db.init_db(conn)
        lb_row = conn.execute(
            "SELECT id, node_id, project_id, type, listen_port FROM load_balancers WHERE id = ?",
            (lb_id,),
        ).fetchone()
        if not lb_row:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "load balancer not found"}}), 404

        operation = operation_service.create_operation(
            action_type="remove_lb_node",
            targets=[str(_row_get(lb_row, "node_id") or "")],
            parameters={
                "load_balancer_id": _row_get(lb_row, "id"),
                "project_id": _row_get(lb_row, "project_id"),
                "type": _row_get(lb_row, "type"),
                "listen_port": _row_get(lb_row, "listen_port"),
            },
            initiator="load_balancer",
            conn=conn,
        )
        ok = infrastructure_service.delete_load_balancer(lb_id, conn)
        if not ok:
            return jsonify({"error": {"code": "NOT_FOUND", "message": "load balancer not found"}}), 404
        event_service.append_event(
            tick=int(time.time()),
            event_type="load_balancer",
            message=f"load balancer removed: {lb_id}",
            payload={"load_balancer_id": lb_id, "node_id": _row_get(lb_row, "node_id")},
            conn=conn,
        )
        return jsonify({"ok": True, "operation": operation})
    finally:
        conn.close()


@bp.put("/load-balancers/<lb_id>")
def put_load_balancer(lb_id: str):
    body = request.get_json(silent=True) or {}
    conn = db.connect()
    try:
        db.init_db(conn)
        try:
            lb = infrastructure_service.update_load_balancer(lb_id, body, conn)
        except ValueError as exc:
            message = str(exc)
            if message == "load balancer not found":
                return jsonify({"error": {"code": "NOT_FOUND", "message": message}}), 404
            return _bad_request(message)
        event_service.append_event(
            tick=int(time.time()),
            event_type="load_balancer",
            message=f"load balancer updated: {lb_id}",
            payload={"load_balancer_id": lb_id, "project_id": lb.get("projectId"), "node_id": lb.get("nodeId")},
            conn=conn,
        )
        return jsonify({"loadBalancer": lb})
    finally:
        conn.close()


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


def _simulation_guard():
    if runtime_config.is_simulation_enabled():
        return None
    return jsonify(
        {
            "error": {
                "code": "FEATURE_DISABLED",
                "message": "simulation mode is disabled",
            }
        }
    ), 404


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return default
