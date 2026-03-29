from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from app.core import actions as action_catalog
from app.persistence import db
from app.services import autonomy_service, event_service, operation_service, policy_service

HOUR_TICKS = 3600
BLOCKED_EVENT_COOLDOWN_TICKS = 30


def on_tick(
    world_state: Dict[str, Any],
    execute_action_fn: Optional[Any] = None,
    conn: Any = None,
) -> Dict[str, Any]:
    if not isinstance(world_state, dict):
        return world_state
    tick = _safe_tick(world_state.get("tick"))
    servers = world_state.get("servers")
    if not isinstance(servers, dict):
        return world_state

    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    policies = policy_service.list_runnable_policies(conn=conn)
    for policy in policies:
        _process_policy(policy, world_state, tick, conn)

    conn.commit()
    if close_conn:
        conn.close()
    return world_state


def dry_run(
    policy: Dict[str, Any],
    world_state: Dict[str, Any],
    conn: Any = None,
) -> Dict[str, Any]:
    tick = _safe_tick((world_state or {}).get("tick"))
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    result = _dry_run_policy(policy, world_state, tick, conn)

    if close_conn:
        conn.close()
    return result


def run_policy(
    policy: Dict[str, Any],
    world_state: Dict[str, Any],
    conn: Any = None,
    force: bool = False,
    initiator: str = "manual",
) -> Dict[str, Any]:
    tick = _safe_tick((world_state or {}).get("tick"))
    close_conn = False
    if conn is None:
        conn = db.connect()
        close_conn = True
    db.init_db(conn)

    operations: List[Dict[str, Any]] = []
    decisions: List[Dict[str, Any]] = []
    policy_id = str(policy.get("id") or "")
    policy_name = str(policy.get("name") or "")

    targets = _resolve_targets(policy, world_state)
    for target in targets:
        server = (world_state or {}).get("servers", {}).get(target)
        if not isinstance(server, dict):
            continue
        if not _is_server_runnable(server):
            continue

        matched, details = _evaluate_conditions(
            policy_id, policy, target, server, tick, conn, mutate=False
        )
        if not matched:
            decisions.append(
                {
                    "target": target,
                    "decision": "no_match",
                    **details,
                }
            )
            continue

        action_type, action_reason, blocked = _select_action(policy, world_state, target, conn)
        if action_type is None:
            decision = "blocked" if blocked else "no_action"
            decisions.append(
                {
                    "target": target,
                    "decision": decision,
                    "reasons": [action_reason] if action_reason else [],
                    **details,
                }
            )
            continue

        if not force:
            allowed, guard_reasons = _guardrails_allow(
                policy, target, tick, conn
            )
            if not allowed:
                decisions.append(
                    {
                        "target": target,
                        "decision": "blocked",
                        "reasons": guard_reasons,
                        **details,
                    }
                )
                continue

        operation = operation_service.create_operation(
            action_type=action_type,
            targets=[target],
            initiator=initiator,
            policy_id=policy_id,
            policy_version=policy.get("version"),
            policy_name=policy_name,
            conn=conn,
        )
        operation_id = operation.get("id") if isinstance(operation, dict) else None
        operations.append(operation)
        _record_fire(conn, policy_id, target, tick)
        decisions.append(
            {
                "target": target,
                "decision": "queued",
                "action": action_type,
                "operation_id": operation_id,
                **details,
            }
        )
        _emit_policy_event(
            tick=tick,
            decision="queued",
            policy=policy,
            target=target,
            action=action_type,
            reasons=["manual_run"],
            conn=conn,
            operation_id=operation_id,
        )

    if close_conn:
        conn.close()
    return {"operations": operations, "decisions": decisions}


def _dry_run_policy(
    policy: Dict[str, Any],
    world_state: Dict[str, Any],
    tick: int,
    conn: Any,
) -> Dict[str, Any]:
    policy_id = str(policy.get("id") or "")
    name = str(policy.get("name") or "")
    mode = str(policy.get("mode") or "ADVISE_ONLY")
    priority = int(policy.get("priority") or 0)

    targets = _resolve_targets(policy, world_state)
    evaluations: List[Dict[str, Any]] = []

    for target in targets:
        server = (world_state or {}).get("servers", {}).get(target)
        if not isinstance(server, dict):
            continue
        if not _is_server_runnable(server):
            continue

        matched, details = _evaluate_conditions(
            policy_id, policy, target, server, tick, conn, mutate=False
        )
        if not matched:
            evaluations.append(
                {"target": target, "matched": False, "decision": "no_match", **details}
            )
            continue

        action_type, action_reason, blocked = _select_action(policy, world_state, target, conn)
        if action_type is None:
            decision = "blocked" if blocked else "no_action"
            evaluations.append(
                {
                    "target": target,
                    "matched": True,
                    "decision": decision,
                    "reasons": [action_reason] if action_reason else [],
                    **details,
                }
            )
            continue

        allowed, guard_reasons = _guardrails_allow(policy, target, tick, conn)
        if not allowed:
            evaluations.append(
                {
                    "target": target,
                    "matched": True,
                    "decision": "blocked",
                    "action": action_type,
                    "reasons": guard_reasons,
                    **details,
                }
            )
            continue

        decision = "suggested" if mode == "ADVISE_ONLY" else "queued"
        evaluations.append(
            {
                "target": target,
                "matched": True,
                "decision": decision,
                "action": action_type,
                **details,
            }
        )

    autonomy_enabled = autonomy_service.is_autonomy_enabled()
    return {
        "tick": tick,
        "autonomy_enabled": bool(autonomy_enabled),
        "policy": {"id": policy_id, "name": name, "mode": mode, "priority": priority},
        "evaluations": evaluations,
    }


def _process_policy(
    policy: Dict[str, Any],
    world_state: Dict[str, Any],
    tick: int,
    conn: Any,
) -> None:
    policy_id = str(policy.get("id") or "")
    if not policy_id:
        return

    mode = str(policy.get("mode") or "ADVISE_ONLY")
    autonomy_enabled = autonomy_service.is_autonomy_enabled()

    targets = _resolve_targets(policy, world_state)
    for target in targets:
        server = (world_state or {}).get("servers", {}).get(target)
        if not isinstance(server, dict):
            continue
        if not _is_server_runnable(server):
            continue

        matched, _details = _evaluate_conditions(
            policy_id, policy, target, server, tick, conn, mutate=True
        )
        if not matched:
            continue

        action_type, action_reason, blocked = _select_action(policy, world_state, target, conn)
        if action_type is None:
            if blocked and _should_emit_blocked(conn, policy_id, target, tick):
                _emit_policy_event(
                    tick=tick,
                    decision="blocked",
                    policy=policy,
                    target=target,
                    action=None,
                    reasons=[action_reason] if action_reason else [],
                    conn=conn,
                )
                _record_blocked(conn, policy_id, target, tick)
            continue

        allowed, guard_reasons = _guardrails_allow(policy, target, tick, conn)
        if not allowed:
            if _should_emit_blocked(conn, policy_id, target, tick):
                _emit_policy_event(
                    tick=tick,
                    decision="blocked",
                    policy=policy,
                    target=target,
                    action=action_type,
                    reasons=guard_reasons,
                    conn=conn,
                )
                _record_blocked(conn, policy_id, target, tick)
            continue

        if mode == "ADVISE_ONLY":
            _emit_policy_event(
                tick=tick,
                decision="suggested",
                policy=policy,
                target=target,
                action=action_type,
                reasons=[],
                conn=conn,
            )
            _record_fire(conn, policy_id, target, tick)
            continue

        if not autonomy_enabled:
            continue

        operation = operation_service.create_operation(
            action_type=action_type,
            targets=[target],
            initiator="policy",
            policy_id=policy_id,
            policy_version=policy.get("version"),
            policy_name=str(policy.get("name") or ""),
            conn=conn,
        )
        operation_id = operation.get("id") if isinstance(operation, dict) else None
        _emit_policy_event(
            tick=tick,
            decision="queued",
            policy=policy,
            target=target,
            action=action_type,
            reasons=[],
            conn=conn,
            operation_id=operation_id,
        )
        _record_fire(conn, policy_id, target, tick)


def _evaluate_conditions(
    policy_id: str,
    policy: Dict[str, Any],
    target: str,
    server: Dict[str, Any],
    tick: int,
    conn: Any,
    mutate: bool,
) -> Tuple[bool, Dict[str, Any]]:
    conditions = policy.get("conditions")
    if not isinstance(conditions, dict):
        return True, {"conditions": []}
    items = conditions.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return True, {"conditions": []}

    op = str(conditions.get("op") or "AND")
    if op not in ("AND", "OR"):
        op = "AND"

    if mutate:
        _prune_condition_state(conn, policy_id, target, tick)
    existing = _load_condition_state(conn, policy_id, target)
    details: List[Dict[str, Any]] = []
    satisfied_flags: List[bool] = []

    for idx, cond in enumerate(items):
        if not isinstance(cond, dict):
            satisfied_flags.append(False)
            details.append({"index": idx, "ok": False, "reason": "invalid_condition"})
            continue

        metric = str(cond.get("metric") or "")
        op_str = str(cond.get("op") or "")
        value = cond.get("value")
        duration = cond.get("durationSec")

        raw_value = _as_number(server.get(metric), 0.0)
        target_value = _as_number(value, 0.0)
        now_true = _compare(raw_value, op_str, target_value)

        duration_ticks = _duration_to_ticks(duration)
        true_since = existing.get(idx)
        if true_since is not None and true_since > tick:
            if mutate:
                _delete_condition_state(conn, policy_id, target, idx)
            true_since = None

        if now_true:
            if true_since is None:
                true_since = tick
                if mutate:
                    _upsert_condition_state(conn, policy_id, target, idx, tick)
        else:
            if true_since is not None and mutate:
                _delete_condition_state(conn, policy_id, target, idx)
            true_since = None

        satisfied = False
        remaining = 0
        if now_true:
            if duration_ticks <= 1:
                satisfied = True
            elif true_since is not None:
                have = tick - true_since + 1
                satisfied = have >= duration_ticks
                remaining = max(0, duration_ticks - have)

        satisfied_flags.append(bool(satisfied))
        details.append(
            {
                "index": idx,
                "metric": metric,
                "op": op_str,
                "value": target_value,
                "current": raw_value,
                "durationTicks": duration_ticks,
                "trueSinceTick": true_since,
                "satisfied": bool(satisfied),
                "remainingTicks": int(remaining),
            }
        )

    matched = any(satisfied_flags) if op == "OR" else all(satisfied_flags)
    return bool(matched), {"conditions": details, "op": op}


def _select_action(
    policy: Dict[str, Any],
    world_state: Dict[str, Any],
    target: str,
    conn: Any,
) -> Tuple[Optional[str], str, bool]:
    actions_raw = policy.get("actions")
    if not isinstance(actions_raw, list):
        return None, "", False

    run_mode = operation_service.get_run_mode()
    for step in actions_raw:
        if not isinstance(step, dict):
            continue
        action_type = step.get("type")
        if not isinstance(action_type, str) or not action_type:
            continue
        spec = action_catalog.get_action(action_type, conn)
        if spec is None:
            continue
        availability = step.get("availability") or spec.availability
        capability = step.get("capability") or spec.capability
        if availability != "available":
            continue
        if run_mode == "simulation" and capability == "probe":
            continue

        allowed, reason, blocking, noop = action_catalog.evaluate_action(
            action_type, world_state, target, conn
        )
        if noop:
            continue
        if allowed:
            return action_type, "", False
        if blocking:
            return None, reason, True
        continue
    return None, "", False


def _guardrails_allow(
    policy: Dict[str, Any],
    target: str,
    tick: int,
    conn: Any,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    guard_raw = policy.get("guardrails") if isinstance(policy, dict) else None
    guard: Dict[str, Any] = guard_raw if isinstance(guard_raw, dict) else {}
    cooldown_ticks = _duration_to_ticks(guard.get("cooldownSec"))
    max_per_hour = int(guard.get("maxPerHour") or 0)

    runtime = _load_runtime(conn, str(policy.get("id") or ""), target, tick)
    last_fire = runtime.get("last_fire_tick")
    if cooldown_ticks > 0 and last_fire is not None:
        if tick - int(last_fire) < cooldown_ticks:
            reasons.append("cooldown")
    if max_per_hour <= 0:
        reasons.append("max_per_hour")

    window_start = runtime.get("window_start_tick")
    window_count = int(runtime.get("window_count") or 0)
    if window_start is not None and tick - int(window_start) >= HOUR_TICKS:
        window_start = None
        window_count = 0
    if window_start is not None and window_count >= max_per_hour:
        reasons.append("max_per_hour")

    if reasons:
        return False, reasons
    return True, []


def _resolve_targets(policy: Dict[str, Any], world_state: Dict[str, Any]) -> List[str]:
    servers = (world_state or {}).get("servers", {})
    all_nodes = [str(k) for k in servers.keys()]

    scope = policy.get("scope")
    if not isinstance(scope, dict):
        return all_nodes
    scope_type = scope.get("type")
    if scope_type == "nodes":
        node_ids = scope.get("nodeIds")
        if not isinstance(node_ids, list):
            return []
        wanted = [str(v) for v in node_ids if isinstance(v, str) and v.strip()]
        return [node_id for node_id in wanted if node_id in servers]
    if scope_type == "all" or scope_type is None:
        return all_nodes
    return []


def _is_server_runnable(server: Dict[str, Any]) -> bool:
    status = server.get("status")
    return status in (None, "running")


def _emit_policy_event(
    tick: int,
    decision: str,
    policy: Dict[str, Any],
    target: str,
    action: Optional[str],
    reasons: List[str],
    conn: Any,
    operation_id: Optional[str] = None,
) -> None:
    policy_id = str(policy.get("id") or "")
    name = str(policy.get("name") or "")
    version = int(policy.get("version") or 0)
    mode = str(policy.get("mode") or "ADVISE_ONLY")

    reason_text = ",".join([r for r in reasons if r])
    action_text = action or "-"
    message = f"policy {decision}: {name} on {target} ({action_text})"
    if reason_text:
        message = f"{message} [{reason_text}]"

    payload: Dict[str, Any] = {
        "policy_id": policy_id,
        "policy_name": name,
        "policy_version": version,
        "mode": mode,
        "target": target,
        "decision": decision,
    }
    if action:
        payload["actions"] = [action]
    if reasons:
        payload["reasons"] = reasons
    if operation_id:
        payload["operation_id"] = operation_id

    event_service.append_event(
        tick=int(tick),
        event_type="policy",
        message=message,
        payload=payload,
        conn=conn,
    )


def _load_runtime(conn: Any, policy_id: str, target: str, tick: int) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT last_fire_tick, window_start_tick, window_count, last_blocked_tick
        FROM policy_runtime
        WHERE policy_id = ? AND target = ?
        """,
        (policy_id, target),
    ).fetchone()
    if not row:
        return {
            "last_fire_tick": None,
            "window_start_tick": None,
            "window_count": 0,
            "last_blocked_tick": None,
        }

    last_fire = row["last_fire_tick"]
    window_start = row["window_start_tick"]
    last_blocked = row["last_blocked_tick"]
    if any(
        value is not None and int(value) > tick
        for value in (last_fire, window_start, last_blocked)
    ):
        conn.execute(
            "DELETE FROM policy_runtime WHERE policy_id = ? AND target = ?",
            (policy_id, target),
        )
        return {
            "last_fire_tick": None,
            "window_start_tick": None,
            "window_count": 0,
            "last_blocked_tick": None,
        }

    return {
        "last_fire_tick": last_fire,
        "window_start_tick": window_start,
        "window_count": row["window_count"],
        "last_blocked_tick": last_blocked,
    }


def _record_fire(conn: Any, policy_id: str, target: str, tick: int) -> None:
    runtime = _load_runtime(conn, policy_id, target, tick)
    window_start = runtime["window_start_tick"]
    window_count = int(runtime["window_count"] or 0)
    if window_start is None or tick - int(window_start) >= HOUR_TICKS:
        window_start = tick
        window_count = 0
    window_count += 1
    conn.execute(
        """
        INSERT INTO policy_runtime (policy_id, target, last_fire_tick, window_start_tick, window_count, last_blocked_tick)
        VALUES (?, ?, ?, ?, ?, COALESCE((SELECT last_blocked_tick FROM policy_runtime WHERE policy_id = ? AND target = ?), NULL))
        ON CONFLICT(policy_id, target) DO UPDATE SET
            last_fire_tick = excluded.last_fire_tick,
            window_start_tick = excluded.window_start_tick,
            window_count = excluded.window_count
        """,
        (policy_id, target, tick, window_start, window_count, policy_id, target),
    )


def _record_blocked(conn: Any, policy_id: str, target: str, tick: int) -> None:
    conn.execute(
        """
        INSERT INTO policy_runtime (policy_id, target, last_fire_tick, window_start_tick, window_count, last_blocked_tick)
        VALUES (
            ?, ?,
            (SELECT last_fire_tick FROM policy_runtime WHERE policy_id = ? AND target = ?),
            (SELECT window_start_tick FROM policy_runtime WHERE policy_id = ? AND target = ?),
            COALESCE((SELECT window_count FROM policy_runtime WHERE policy_id = ? AND target = ?), 0),
            ?
        )
        ON CONFLICT(policy_id, target) DO UPDATE SET
            last_blocked_tick = excluded.last_blocked_tick
        """,
        (policy_id, target, policy_id, target, policy_id, target, policy_id, target, tick),
    )


def _should_emit_blocked(conn: Any, policy_id: str, target: str, tick: int) -> bool:
    runtime = _load_runtime(conn, policy_id, target, tick)
    last_blocked = runtime.get("last_blocked_tick")
    if last_blocked is None:
        return True
    return tick - int(last_blocked) >= BLOCKED_EVENT_COOLDOWN_TICKS


def _load_condition_state(conn: Any, policy_id: str, target: str) -> Dict[int, int]:
    cursor = conn.execute(
        """
        SELECT condition_index, true_since_tick
        FROM policy_condition_state
        WHERE policy_id = ? AND target = ?
        """,
        (policy_id, target),
    )
    state: Dict[int, int] = {}
    for row in cursor:
        idx = row["condition_index"]
        ts = row["true_since_tick"]
        if isinstance(idx, int) and isinstance(ts, int):
            state[idx] = ts
    return state


def _prune_condition_state(conn: Any, policy_id: str, target: str, tick: int) -> None:
    conn.execute(
        "DELETE FROM policy_condition_state WHERE policy_id = ? AND target = ? AND true_since_tick > ?",
        (policy_id, target, tick),
    )


def _upsert_condition_state(conn: Any, policy_id: str, target: str, index: int, tick: int) -> None:
    conn.execute(
        """
        INSERT INTO policy_condition_state (policy_id, target, condition_index, true_since_tick)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(policy_id, target, condition_index) DO UPDATE SET true_since_tick = excluded.true_since_tick
        """,
        (policy_id, target, int(index), int(tick)),
    )


def _delete_condition_state(conn: Any, policy_id: str, target: str, index: int) -> None:
    conn.execute(
        "DELETE FROM policy_condition_state WHERE policy_id = ? AND target = ? AND condition_index = ?",
        (policy_id, target, int(index)),
    )


def _duration_to_ticks(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        if float(value) <= 0:
            return 0
        return int(max(1, math.ceil(float(value))))
    return 0


def _safe_tick(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    return 0


def _as_number(value: Any, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return float(default)


def _compare(left: float, op: str, right: float) -> bool:
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    return False
