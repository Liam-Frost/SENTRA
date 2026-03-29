from __future__ import annotations


def _register_agent(client):
    response = client.post(
        "/api/agents/register",
        json={
            "agent_id": "agent-test-1",
            "node_id": "node-a",
            "hostname": "node-a",
            "ip": "10.0.0.1",
            "os": "linux",
            "arch": "amd64",
            "version": "1.0.0",
        },
    )
    assert response.status_code == 200
    return response.get_json()


def test_agent_register_heartbeat_metrics_and_nodes(client, monkeypatch):
    monkeypatch.setenv("SENTRA_SIM_ENABLED", "false")
    registered = _register_agent(client)
    assert registered["agentId"] == "agent-test-1"
    assert registered["nodeId"] == "node-a"

    heartbeat = client.post(
        "/api/agents/heartbeat",
        json={"agent_id": "agent-test-1", "status": "online", "payload": {"uptime": 123}},
    )
    assert heartbeat.status_code == 200

    metrics = client.post(
        "/api/agents/metrics",
        json={
            "agent_id": "agent-test-1",
            "metrics": {
                "cpu": 53.2,
                "memory": 41.0,
                "disk": 33.0,
                "netIn": 1234,
                "netOut": 567,
                "temp": 49,
                "errorRate": 0.2,
                "health": 92,
                "power": 210,
            },
        },
    )
    assert metrics.status_code == 200

    nodes = client.get("/api/nodes")
    assert nodes.status_code == 200
    payload = nodes.get_json()
    assert len(payload["nodes"]) == 1
    assert payload["nodes"][0]["id"] == "node-a"
    assert payload["nodes"][0]["metrics"]["cpu"] == 53.2

    state = client.get("/api/state")
    assert state.status_code == 200
    world = state.get_json()
    assert "node-a" in world["servers"]


def test_operation_agent_command_flow(client, monkeypatch):
    monkeypatch.setenv("SENTRA_SIM_ENABLED", "false")
    _register_agent(client)

    created = client.post(
        "/api/operations",
        json={
            "action": "run_command",
            "targets": ["node-a"],
            "parameters": {"command": "uptime"},
            "initiator": "test",
        },
    )
    assert created.status_code == 200
    operation_id = created.get_json()["operation"]["id"]

    command = client.get("/api/agents/commands/next", query_string={"agent_id": "agent-test-1"})
    assert command.status_code == 200
    command_payload = command.get_json()["command"]
    assert command_payload["operationId"] == operation_id
    run_id = command_payload["runId"]

    log_resp = client.post(
        f"/api/agents/commands/{run_id}/logs",
        json={"stream": "stdout", "message": "starting"},
    )
    assert log_resp.status_code == 200

    done = client.post(
        f"/api/agents/commands/{run_id}/result",
        json={"status": "succeeded", "output": "ok", "exit_code": 0},
    )
    assert done.status_code == 200
    assert done.get_json()["operationStatus"] == "succeeded"

    op = client.get(f"/api/operations/{operation_id}")
    assert op.status_code == 200
    body = op.get_json()
    assert body["operation"]["status"] == "succeeded"
    assert body["runs"][0]["status"] == "succeeded"

    logs = client.get(f"/api/operations/{operation_id}/logs")
    assert logs.status_code == 200
    assert len(logs.get_json()["logs"]) == 1


def test_projects_and_load_balancers(client, monkeypatch):
    monkeypatch.setenv("SENTRA_SIM_ENABLED", "false")
    _register_agent(client)
    node_b = client.post(
        "/api/nodes",
        json={"id": "node-b", "hostname": "node-b", "ip": "10.0.0.2", "status": "online"},
    )
    assert node_b.status_code == 200

    project = client.post("/api/projects", json={"name": "alpha"})
    assert project.status_code == 200
    project_id = project.get_json()["project"]["id"]

    updated = client.put(f"/api/projects/{project_id}", json={"name": "alpha-renamed", "description": "core"})
    assert updated.status_code == 200
    assert updated.get_json()["project"]["name"] == "alpha-renamed"

    lb = client.post(
        "/api/load-balancers",
        json={
            "projectId": project_id,
            "nodeId": "node-a",
            "type": "nginx",
            "listenPort": 8080,
        },
    )
    assert lb.status_code == 200
    lb_body = lb.get_json()
    assert lb_body["loadBalancer"]["projectId"] == project_id
    lb_id = lb_body["loadBalancer"]["id"]

    listed = client.get("/api/load-balancers")
    assert listed.status_code == 200
    assert len(listed.get_json()["loadBalancers"]) == 1

    batch = client.post(
        "/api/load-balancers",
        json={
            "projectId": project_id,
            "nodeIds": ["node-a", "node-b"],
            "type": "traefik",
            "listenPort": 9000,
        },
    )
    assert batch.status_code == 200
    batch_body = batch.get_json()
    assert len(batch_body["loadBalancers"]) == 2
    assert len(batch_body["operations"]) == 2

    deleted = client.delete(f"/api/load-balancers/{lb_id}")
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True

    blocked_delete = client.delete(f"/api/projects/{project_id}")
    assert blocked_delete.status_code == 400

    listed_after_delete = client.get("/api/load-balancers")
    remaining = listed_after_delete.get_json()["loadBalancers"]
    for item in remaining:
        client.delete(f"/api/load-balancers/{item['id']}")

    project_deleted = client.delete(f"/api/projects/{project_id}")
    assert project_deleted.status_code == 200
    assert project_deleted.get_json()["ok"] is True
