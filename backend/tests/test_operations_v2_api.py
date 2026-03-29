from __future__ import annotations


def _register_agent(client):
    response = client.post(
        "/api/agents/register",
        json={
            "agent_id": "agent-v2-1",
            "node_id": "node-v2-a",
            "hostname": "node-v2-a",
            "ip": "10.1.0.1",
            "os": "linux",
            "arch": "amd64",
            "version": "1.0.0",
        },
    )
    assert response.status_code == 200


def test_operation_templates_execute_through_agent(client, monkeypatch):
    monkeypatch.setenv("SENTRA_SIM_ENABLED", "false")
    _register_agent(client)

    template = client.post(
        "/api/operation-templates",
        json={
            "name": "Restart app",
            "description": "restart and verify",
            "steps": [
                {"name": "Restart", "command": "echo restart", "timeoutSec": 15},
                {"name": "Verify", "command": "echo verify", "timeoutSec": 15},
            ],
        },
    )
    assert template.status_code == 200
    template_id = template.get_json()["template"]["id"]

    executed = client.post(
        f"/api/operation-templates/{template_id}/execute",
        json={"targets": ["node-v2-a"], "initiator": "tester"},
    )
    assert executed.status_code == 200
    execution_id = executed.get_json()["execution"]["id"]

    execution_list = client.get("/api/operation-executions")
    assert execution_list.status_code == 200
    assert len(execution_list.get_json()["executions"]) == 1

    command = client.get("/api/agents/commands/next", query_string={"agent_id": "agent-v2-1"})
    assert command.status_code == 200
    command_payload = command.get_json()["command"]
    assert command_payload["action"] == "template_execution"
    assert len(command_payload["parameters"]["steps"]) == 2
    run_id = command_payload["runId"]

    done = client.post(
        f"/api/agents/commands/{run_id}/result",
        json={"status": "succeeded", "output": "restart\nverify", "exit_code": 0},
    )
    assert done.status_code == 200

    detail = client.get(f"/api/operation-executions/{execution_id}")
    assert detail.status_code == 200
    body = detail.get_json()
    assert body["execution"]["id"] == execution_id
    assert body["runs"][0]["status"] == "succeeded"


def test_lb_policy_crud_and_apply(client, monkeypatch):
    monkeypatch.setenv("SENTRA_SIM_ENABLED", "false")
    _register_agent(client)
    node_b = client.post(
        "/api/nodes",
        json={"id": "node-v2-b", "hostname": "node-v2-b", "ip": "10.1.0.2", "status": "online"},
    )
    assert node_b.status_code == 200

    project = client.post("/api/projects", json={"name": "ops-core"})
    assert project.status_code == 200
    project_id = project.get_json()["project"]["id"]

    created = client.post(
        "/api/lb-policies",
        json={
            "projectId": project_id,
            "name": "Primary traffic",
            "status": "draft",
            "drMode": "manual",
            "healthCheckPath": "/healthz",
            "healthCheckIntervalSec": 10,
            "failureThreshold": 3,
            "recoveryThreshold": 2,
            "autoFailback": False,
            "allocations": [
                {"nodeId": "node-v2-a", "enabled": True, "weight": 60, "priority": 1},
                {"nodeId": "node-v2-b", "enabled": True, "weight": 40, "priority": 2},
            ],
        },
    )
    assert created.status_code == 200
    policy_id = created.get_json()["policy"]["id"]

    updated = client.put(
        f"/api/lb-policies/{policy_id}",
        json={
            "projectId": project_id,
            "name": "Primary traffic updated",
            "status": "active",
            "drMode": "weighted-failover",
            "healthCheckPath": "/ready",
            "healthCheckIntervalSec": 15,
            "failureThreshold": 4,
            "recoveryThreshold": 3,
            "autoFailback": True,
            "allocations": [
                {"nodeId": "node-v2-a", "enabled": True, "weight": 50, "priority": 1},
                {"nodeId": "node-v2-b", "enabled": True, "weight": 50, "priority": 2},
            ],
        },
    )
    assert updated.status_code == 200
    assert updated.get_json()["policy"]["drMode"] == "weighted-failover"

    applied = client.post(f"/api/lb-policies/{policy_id}/apply", json={"initiator": "tester"})
    assert applied.status_code == 200
    execution_id = applied.get_json()["execution"]["id"]

    executions = client.get("/api/operation-executions", query_string={"source": "lb_policy_apply"})
    assert executions.status_code == 200
    assert len(executions.get_json()["executions"]) >= 1

    deleted = client.delete(f"/api/lb-policies/{policy_id}")
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True
    assert execution_id
