from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple


_ID_LOCK = threading.RLock()
_ID_COUNTER = 0


def list_nodes(conn: Any) -> Dict[str, List[Dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT
            n.id,
            n.hostname,
            n.ip,
            n.os,
            n.arch,
            n.status,
            n.metadata,
            n.created_at,
            n.updated_at,
            a.id AS agent_id,
            a.version AS agent_version,
            a.last_seen_at,
            m.cpu_load,
            m.mem_used,
            m.disk_used,
            m.net_in,
            m.net_out,
            m.temp,
            m.error_rate,
            m.health,
            m.power,
            m.updated_at AS metrics_updated_at
        FROM nodes n
        LEFT JOIN agents a ON a.node_id = n.id
        LEFT JOIN node_metrics_latest m ON m.node_id = n.id
        ORDER BY n.hostname ASC, n.id ASC
        """
    )
    return {"nodes": [_row_to_node_summary(row) for row in rows]}


def get_node(node_id: str, conn: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(node_id, str) or not node_id.strip():
        return None
    row = conn.execute(
        """
        SELECT
            n.id,
            n.hostname,
            n.ip,
            n.os,
            n.arch,
            n.status,
            n.metadata,
            n.created_at,
            n.updated_at,
            a.id AS agent_id,
            a.version AS agent_version,
            a.last_seen_at,
            m.cpu_load,
            m.mem_used,
            m.disk_used,
            m.net_in,
            m.net_out,
            m.temp,
            m.error_rate,
            m.health,
            m.power,
            m.updated_at AS metrics_updated_at
        FROM nodes n
        LEFT JOIN agents a ON a.node_id = n.id
        LEFT JOIN node_metrics_latest m ON m.node_id = n.id
        WHERE n.id = ?
        """,
        (node_id,),
    ).fetchone()
    if not row:
        return None

    lbs = conn.execute(
        """
        SELECT id, project_id, node_id, type, status, listen_port, config, created_at, updated_at
        FROM load_balancers
        WHERE node_id = ?
        ORDER BY created_at DESC
        """,
        (node_id,),
    )
    node = _row_to_node_summary(row)
    node["loadBalancers"] = [_row_to_lb(item) for item in lbs]
    return node


def register_agent(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    hostname = _normalize_text(payload.get("hostname"))
    node_id_input = _normalize_text(payload.get("node_id") or payload.get("nodeId"))
    agent_id_input = _normalize_text(payload.get("agent_id") or payload.get("agentId"))

    if not hostname and not node_id_input:
        raise ValueError("hostname or node_id is required")

    node_id = node_id_input or _slug(hostname or "node")
    node_id = node_id if node_id else _next_id("node")
    agent_id = agent_id_input or _next_id("agent")

    now_ms = _now_ms()
    node = upsert_node(
        {
            "id": node_id,
            "hostname": hostname or node_id,
            "ip": _normalize_text(payload.get("ip")),
            "os": _normalize_text(payload.get("os")),
            "arch": _normalize_text(payload.get("arch")),
            "status": "online",
            "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        },
        conn=conn,
    )

    version = _normalize_text(payload.get("version"))
    token = _normalize_text(payload.get("token"))
    capabilities = payload.get("capabilities") if isinstance(payload.get("capabilities"), dict) else {}

    conn.execute(
        """
        INSERT INTO agents (id, node_id, hostname, version, token, capabilities, last_seen_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            node_id = excluded.node_id,
            hostname = excluded.hostname,
            version = excluded.version,
            token = excluded.token,
            capabilities = excluded.capabilities,
            last_seen_at = excluded.last_seen_at,
            updated_at = excluded.updated_at
        """,
        (
            agent_id,
            node_id,
            hostname or node_id,
            version,
            token,
            json.dumps(capabilities, ensure_ascii=True),
            now_ms,
            now_ms,
            now_ms,
        ),
    )
    conn.commit()

    return {
        "agentId": agent_id,
        "nodeId": node_id,
        "registeredAt": now_ms,
        "node": node,
    }


def post_heartbeat(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    agent_id = _normalize_text(payload.get("agent_id") or payload.get("agentId"))
    if not agent_id:
        raise ValueError("agent_id is required")

    agent_row = conn.execute(
        "SELECT id, node_id FROM agents WHERE id = ?",
        (agent_id,),
    ).fetchone()
    if not agent_row:
        raise ValueError("agent not found")

    node_id = str(agent_row["node_id"])
    now_ms = _now_ms()
    status = _normalize_text(payload.get("status")) or "online"
    heartbeat_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}

    conn.execute(
        "INSERT INTO node_heartbeats (node_id, agent_id, status, payload, ts) VALUES (?, ?, ?, ?, ?)",
        (node_id, agent_id, status, json.dumps(heartbeat_payload, ensure_ascii=True), now_ms),
    )
    conn.execute(
        "UPDATE agents SET last_seen_at = ?, updated_at = ? WHERE id = ?",
        (now_ms, now_ms, agent_id),
    )
    conn.execute(
        "UPDATE nodes SET status = ?, updated_at = ? WHERE id = ?",
        (status, now_ms, node_id),
    )
    conn.commit()
    return {"ok": True, "nodeId": node_id, "ts": now_ms}


def post_metrics(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    node_id, agent_id = _resolve_node_agent(payload, conn)
    if not node_id:
        raise ValueError("agent_id or node_id is required")

    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else payload
    now_ms = _now_ms()
    ts = _safe_int(payload.get("ts"), now_ms)

    point = {
        "cpu": _safe_float(metrics.get("cpu"), 0.0),
        "memory": _safe_float(metrics.get("memory"), 0.0),
        "disk": _safe_float(metrics.get("disk"), 0.0),
        "netIn": _safe_float(metrics.get("net_in") if "net_in" in metrics else metrics.get("netIn"), 0.0),
        "netOut": _safe_float(metrics.get("net_out") if "net_out" in metrics else metrics.get("netOut"), 0.0),
        "temp": _safe_float(metrics.get("temp"), 0.0),
        "errorRate": _safe_float(
            metrics.get("error_rate") if "error_rate" in metrics else metrics.get("errorRate"),
            0.0,
        ),
        "health": _safe_float(metrics.get("health"), 100.0),
        "power": _safe_float(metrics.get("power"), 0.0),
    }

    conn.execute(
        """
        INSERT INTO node_metrics_latest (
            node_id, cpu_load, mem_used, disk_used, net_in, net_out, temp, error_rate, health, power, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(node_id) DO UPDATE SET
            cpu_load = excluded.cpu_load,
            mem_used = excluded.mem_used,
            disk_used = excluded.disk_used,
            net_in = excluded.net_in,
            net_out = excluded.net_out,
            temp = excluded.temp,
            error_rate = excluded.error_rate,
            health = excluded.health,
            power = excluded.power,
            updated_at = excluded.updated_at
        """,
        (
            node_id,
            point["cpu"],
            point["memory"],
            point["disk"],
            point["netIn"],
            point["netOut"],
            point["temp"],
            point["errorRate"],
            point["health"],
            point["power"],
            ts,
        ),
    )
    conn.execute(
        """
        INSERT INTO node_metric_samples (
            node_id, cpu_load, mem_used, disk_used, net_in, net_out, temp, error_rate, health, power, ts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node_id,
            point["cpu"],
            point["memory"],
            point["disk"],
            point["netIn"],
            point["netOut"],
            point["temp"],
            point["errorRate"],
            point["health"],
            point["power"],
            ts,
        ),
    )
    conn.execute(
        "UPDATE nodes SET status = ?, updated_at = ? WHERE id = ?",
        ("online", now_ms, node_id),
    )
    if agent_id:
        conn.execute(
            "UPDATE agents SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (now_ms, now_ms, agent_id),
        )

    conn.commit()
    return {"ok": True, "nodeId": node_id, "ts": ts}


def get_world_state(conn: Any) -> Dict[str, Any]:
    nodes = list_nodes(conn).get("nodes", [])
    servers: Dict[str, Dict[str, Any]] = {}
    incoming_traffic = 0.0
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
        load = _safe_float(metrics.get("cpu"), 0.0)
        incoming_traffic += load
        status = str(node.get("status") or "running")
        if status not in {"running", "booting", "restarting", "thermal_shutdown", "off"}:
            status = "running" if status == "online" else "off" if status == "offline" else "running"
        temp = _safe_float(metrics.get("temp"), 0.0)
        health = _safe_float(metrics.get("health"), 100.0)
        servers[node_id] = {
            "load": load,
            "temp": temp,
            "error_rate": _safe_float(metrics.get("errorRate"), 0.0),
            "power": _safe_float(metrics.get("power"), 0.0),
            "health": health,
            "cooling": bool(temp > 40.0),
            "cooling_level": min(1.0, max(0.0, temp / 100.0)),
            "status": status,
        }

    return {
        "tick": int(time.time()),
        "incoming_traffic": round(incoming_traffic, 2),
        "servers": servers,
        "autonomy_enabled": False,
    }


def get_dashboard(conn: Any) -> Dict[str, Any]:
    nodes = list_nodes(conn).get("nodes", [])
    total = len(nodes)
    online = sum(1 for node in nodes if str(node.get("status") or "").lower() in {"online", "running"})
    offline = total - online
    incidents = sum(1 for node in nodes if _node_incident(node))
    cpu = [_safe_float((node.get("metrics") or {}).get("cpu"), 0.0) for node in nodes]
    mem = [_safe_float((node.get("metrics") or {}).get("memory"), 0.0) for node in nodes]
    disk = [_safe_float((node.get("metrics") or {}).get("disk"), 0.0) for node in nodes]
    project_count_row = conn.execute("SELECT COUNT(*) AS count FROM projects").fetchone()
    lb_count_row = conn.execute("SELECT COUNT(*) AS count FROM load_balancers").fetchone()
    policy_rows = conn.execute("SELECT status FROM lb_policies")
    template_count_row = conn.execute("SELECT COUNT(*) AS count FROM operation_templates").fetchone()
    execution_rows = conn.execute(
        "SELECT status, created_at, parameters, targets FROM operations WHERE action_type = ? ORDER BY created_at DESC LIMIT 5",
        ("template_execution",),
    )

    policies = list(policy_rows)
    recent_executions = []
    total_executions = 0
    running_executions = 0
    queued_executions = 0
    for row in conn.execute(
        "SELECT status, created_at, parameters FROM operations WHERE action_type = ? ORDER BY created_at DESC",
        ("template_execution",),
    ):
        total_executions += 1
        status = str(row["status"])
        if status == "running":
            running_executions += 1
        if status == "queued":
            queued_executions += 1

    for row in execution_rows:
        params = _json_dict(_row_get(row, "parameters"))
        targets = _json_list(_row_get(row, "targets"))
        recent_executions.append(
            {
                "status": row["status"],
                "createdAt": int(row["created_at"]),
                "templateId": params.get("template_id"),
                "templateName": params.get("template_name"),
                "targetCount": len(targets),
            }
        )

    return {
        "summary": {
            "totalNodes": total,
            "onlineNodes": online,
            "offlineNodes": offline,
            "incidentNodes": incidents,
            "avgCpu": round(sum(cpu) / total, 2) if total > 0 else 0.0,
            "avgMemory": round(sum(mem) / total, 2) if total > 0 else 0.0,
            "avgDisk": round(sum(disk) / total, 2) if total > 0 else 0.0,
            "projects": int(_row_get(project_count_row, "count", 0) or 0),
            "loadBalancers": int(_row_get(lb_count_row, "count", 0) or 0),
            "policies": len(policies),
            "activePolicies": sum(1 for row in policies if str(row["status"]) == "active"),
            "templates": int(_row_get(template_count_row, "count", 0) or 0),
            "executions": total_executions,
            "runningExecutions": running_executions,
            "queuedExecutions": queued_executions,
        },
        "nodes": nodes,
        "recentExecutions": recent_executions,
    }


def create_or_update_node(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    node = upsert_node(payload, conn=conn)
    conn.commit()
    return node


def upsert_node(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    node_id = _normalize_text(payload.get("id") or payload.get("node_id") or payload.get("nodeId"))
    hostname = _normalize_text(payload.get("hostname"))
    if not node_id:
        node_id = _slug(hostname or "node") or _next_id("node")
    if not hostname:
        hostname = node_id

    ip = _normalize_text(payload.get("ip"))
    os_name = _normalize_text(payload.get("os"))
    arch = _normalize_text(payload.get("arch"))
    status = _normalize_text(payload.get("status")) or "online"
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

    existing = conn.execute("SELECT id, created_at FROM nodes WHERE id = ?", (node_id,)).fetchone()
    now_ms = _now_ms()
    created_at = int(existing["created_at"]) if existing and existing.get("created_at") is not None else now_ms

    conn.execute(
        """
        INSERT INTO nodes (id, hostname, ip, os, arch, status, metadata, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            hostname = excluded.hostname,
            ip = excluded.ip,
            os = excluded.os,
            arch = excluded.arch,
            status = excluded.status,
            metadata = excluded.metadata,
            updated_at = excluded.updated_at
        """,
        (
            node_id,
            hostname,
            ip,
            os_name,
            arch,
            status,
            json.dumps(metadata, ensure_ascii=True),
            created_at,
            now_ms,
        ),
    )
    row = conn.execute(
        """
        SELECT
            n.id,
            n.hostname,
            n.ip,
            n.os,
            n.arch,
            n.status,
            n.metadata,
            n.created_at,
            n.updated_at,
            a.id AS agent_id,
            a.version AS agent_version,
            a.last_seen_at,
            m.cpu_load,
            m.mem_used,
            m.disk_used,
            m.net_in,
            m.net_out,
            m.temp,
            m.error_rate,
            m.health,
            m.power,
            m.updated_at AS metrics_updated_at
        FROM nodes n
        LEFT JOIN agents a ON a.node_id = n.id
        LEFT JOIN node_metrics_latest m ON m.node_id = n.id
        WHERE n.id = ?
        """,
        (node_id,),
    ).fetchone()
    return _row_to_node_summary(row) if row else {"id": node_id, "hostname": hostname}


def list_projects(conn: Any) -> Dict[str, List[Dict[str, Any]]]:
    rows = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM projects ORDER BY created_at DESC"
    )
    return {
        "projects": [
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]
    }


def create_project(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    name = _normalize_text(payload.get("name"))
    if not name:
        raise ValueError("name is required")
    project_id = _normalize_text(payload.get("id")) or _next_id("proj")
    description = _normalize_text(payload.get("description"))
    now_ms = _now_ms()
    conn.execute(
        """
        INSERT INTO projects (id, name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (project_id, name, description, now_ms, now_ms),
    )
    conn.commit()
    return {
        "id": project_id,
        "name": name,
        "description": description,
        "createdAt": now_ms,
        "updatedAt": now_ms,
    }


def update_project(project_id: str, payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    existing = conn.execute(
        "SELECT id, name, description, created_at, updated_at FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if not existing:
        raise ValueError("project not found")

    name = _normalize_text(payload.get("name")) or str(existing["name"])
    description = _normalize_text(payload.get("description"))
    if description is None and _row_get(existing, "description") is not None and "description" not in payload:
        description = str(existing["description"])
    if not name:
        raise ValueError("name is required")

    now_ms = _now_ms()
    conn.execute(
        "UPDATE projects SET name = ?, description = ?, updated_at = ? WHERE id = ?",
        (name, description, now_ms, project_id),
    )
    conn.commit()
    return {
        "id": str(existing["id"]),
        "name": name,
        "description": description,
        "createdAt": int(existing["created_at"]),
        "updatedAt": now_ms,
    }


def delete_project(project_id: str, conn: Any) -> bool:
    existing = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not existing:
        return False

    lb_count_row = conn.execute(
        "SELECT COUNT(*) AS count FROM load_balancers WHERE project_id = ?",
        (project_id,),
    ).fetchone()
    lb_count = int(_row_get(lb_count_row, "count", 0) or 0)
    if lb_count > 0:
        raise ValueError("project still has load balancer instances")

    cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    return cursor.rowcount > 0


def list_load_balancers(
    conn: Any,
    *,
    project_id: Optional[str] = None,
    node_id: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    sql = """
        SELECT id, project_id, node_id, type, status, listen_port, config, created_at, updated_at
        FROM load_balancers
    """
    clauses: List[str] = []
    params: List[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        params.append(project_id)
    if node_id:
        clauses.append("node_id = ?")
        params.append(node_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params)
    return {"loadBalancers": [_row_to_lb(row) for row in rows]}


def create_load_balancer(payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    project_id = _normalize_text(payload.get("projectId") or payload.get("project_id"))
    node_id = _normalize_text(payload.get("nodeId") or payload.get("node_id"))
    lb_type = _normalize_text(payload.get("type"))
    if not project_id:
        raise ValueError("projectId is required")
    if not node_id:
        raise ValueError("nodeId is required")
    if lb_type not in {"nginx", "haproxy", "traefik"}:
        raise ValueError("type must be nginx, haproxy, or traefik")

    project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise ValueError("project not found")
    node = conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if not node:
        raise ValueError("node not found")

    lb_id = _normalize_text(payload.get("id")) or _next_id("lb")
    status = _normalize_text(payload.get("status")) or "running"
    listen_port = payload.get("listenPort")
    if listen_port is None:
        listen_port = payload.get("listen_port")
    port = _safe_int(listen_port, None)
    config_obj = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    now_ms = _now_ms()
    conn.execute(
        """
        INSERT INTO load_balancers (
            id, project_id, node_id, type, status, listen_port, config, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lb_id,
            project_id,
            node_id,
            lb_type,
            status,
            port,
            json.dumps(config_obj, ensure_ascii=True),
            now_ms,
            now_ms,
        ),
    )
    conn.commit()
    return {
        "id": lb_id,
        "projectId": project_id,
        "nodeId": node_id,
        "type": lb_type,
        "status": status,
        "listenPort": port,
        "config": config_obj,
        "createdAt": now_ms,
        "updatedAt": now_ms,
    }


def delete_load_balancer(lb_id: str, conn: Any) -> bool:
    cursor = conn.execute("DELETE FROM load_balancers WHERE id = ?", (lb_id,))
    conn.commit()
    return cursor.rowcount > 0


def update_load_balancer(lb_id: str, payload: Dict[str, Any], conn: Any) -> Dict[str, Any]:
    existing = conn.execute(
        "SELECT id, project_id, node_id, type, status, listen_port, config, created_at, updated_at FROM load_balancers WHERE id = ?",
        (lb_id,),
    ).fetchone()
    if not existing:
        raise ValueError("load balancer not found")

    project_id = _normalize_text(payload.get("projectId") or payload.get("project_id")) or str(existing["project_id"])
    node_id = _normalize_text(payload.get("nodeId") or payload.get("node_id")) or str(existing["node_id"])
    lb_type = _normalize_text(payload.get("type")) or str(existing["type"])
    status = _normalize_text(payload.get("status")) or str(existing["status"])
    if lb_type not in {"nginx", "haproxy", "traefik"}:
        raise ValueError("type must be nginx, haproxy, or traefik")

    project = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise ValueError("project not found")
    node = conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,)).fetchone()
    if not node:
        raise ValueError("node not found")

    listen_port = payload.get("listenPort") if "listenPort" in payload else payload.get("listen_port")
    if listen_port is None:
        listen_port = existing["listen_port"]
    port = _safe_int(listen_port, existing["listen_port"])
    config_obj = payload.get("config") if isinstance(payload.get("config"), dict) else _json_dict(_row_get(existing, "config"))
    now_ms = _now_ms()
    conn.execute(
        """
        UPDATE load_balancers
        SET project_id = ?, node_id = ?, type = ?, status = ?, listen_port = ?, config = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            project_id,
            node_id,
            lb_type,
            status,
            port,
            json.dumps(config_obj, ensure_ascii=True),
            now_ms,
            lb_id,
        ),
    )
    conn.commit()
    return {
        "id": lb_id,
        "projectId": project_id,
        "nodeId": node_id,
        "type": lb_type,
        "status": status,
        "listenPort": port,
        "config": config_obj,
        "createdAt": int(existing["created_at"]),
        "updatedAt": now_ms,
    }


def get_agent(agent_id: str, conn: Any) -> Optional[Dict[str, Any]]:
    row = conn.execute(
        "SELECT id, node_id, hostname, version, token, capabilities, last_seen_at FROM agents WHERE id = ?",
        (agent_id,),
    ).fetchone()
    if not row:
        return None
    capabilities = _json_dict(_row_get(row, "capabilities"))
    return {
        "id": row["id"],
        "nodeId": row["node_id"],
        "hostname": row["hostname"],
        "version": row["version"],
        "token": row["token"],
        "capabilities": capabilities,
        "lastSeenAt": row["last_seen_at"],
    }


def _resolve_node_agent(payload: Dict[str, Any], conn: Any) -> Tuple[Optional[str], Optional[str]]:
    node_id = _normalize_text(payload.get("node_id") or payload.get("nodeId"))
    agent_id = _normalize_text(payload.get("agent_id") or payload.get("agentId"))
    if node_id:
        return node_id, agent_id
    if not agent_id:
        return None, None
    row = conn.execute("SELECT node_id FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        return None, agent_id
    return str(row["node_id"]), agent_id


def _node_incident(node: Dict[str, Any]) -> bool:
    metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
    return (
        _safe_float(metrics.get("temp"), 0.0) > 80.0
        or _safe_float(metrics.get("errorRate"), 0.0) > 5.0
        or _safe_float(metrics.get("health"), 100.0) < 60.0
        or _safe_float(metrics.get("cpu"), 0.0) > 85.0
    )


def _row_to_node_summary(row: Any) -> Dict[str, Any]:
    metadata = _json_dict(_row_get(row, "metadata"))
    return {
        "id": row["id"],
        "hostname": row["hostname"],
        "ip": row["ip"],
        "os": row["os"],
        "arch": row["arch"],
        "status": row["status"],
        "metadata": metadata,
        "agent": {
            "id": _row_get(row, "agent_id"),
            "version": _row_get(row, "agent_version"),
            "lastSeenAt": _row_get(row, "last_seen_at"),
        },
        "metrics": {
            "cpu": _safe_float(_row_get(row, "cpu_load"), 0.0),
            "memory": _safe_float(_row_get(row, "mem_used"), 0.0),
            "disk": _safe_float(_row_get(row, "disk_used"), 0.0),
            "netIn": _safe_float(_row_get(row, "net_in"), 0.0),
            "netOut": _safe_float(_row_get(row, "net_out"), 0.0),
            "temp": _safe_float(_row_get(row, "temp"), 0.0),
            "errorRate": _safe_float(_row_get(row, "error_rate"), 0.0),
            "health": _safe_float(_row_get(row, "health"), 100.0),
            "power": _safe_float(_row_get(row, "power"), 0.0),
            "updatedAt": _row_get(row, "metrics_updated_at"),
        },
        "createdAt": _row_get(row, "created_at"),
        "updatedAt": _row_get(row, "updated_at"),
    }


def _row_to_lb(row: Any) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "projectId": row["project_id"],
        "nodeId": row["node_id"],
        "type": row["type"],
        "status": row["status"],
        "listenPort": row["listen_port"],
        "config": _json_dict(_row_get(row, "config")),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return default


def _safe_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return float(default)
    if isinstance(value, (int, float)):
        return float(value)
    return float(default)


def _safe_int(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _json_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _json_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return decoded if isinstance(decoded, list) else []


def _slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip().lower())
    value = value.strip("-")
    return value[:64]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _next_id(prefix: str) -> str:
    global _ID_COUNTER
    with _ID_LOCK:
        _ID_COUNTER += 1
        return f"{prefix}-{int(time.time() * 1000)}-{_ID_COUNTER}"
