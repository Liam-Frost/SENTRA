def _base_policy(**overrides):
    policy = {
        "name": "Test policy",
        "status": "draft",
        "enabled": False,
        "mode": "ADVISE_ONLY",
        "priority": 100,
        "scope": {"type": "all"},
        "conditions": {"op": "AND", "items": []},
        "actions": [],
        "guardrails": {"cooldownSec": 60, "maxPerHour": 12, "requireApproval": False},
    }
    policy.update(overrides)
    return policy


def test_policy_crud_roundtrip(client):
    create = client.post("/api/policies", json=_base_policy())
    assert create.status_code == 200
    created = create.get_json()["policy"]
    assert isinstance(created.get("id"), str)
    assert created["version"] == 1

    policy_id = created["id"]

    listed = client.get("/api/policies").get_json()["policies"]
    assert any(p.get("id") == policy_id for p in listed)

    fetched = client.get(f"/api/policies/{policy_id}").get_json()
    assert fetched["policy"]["id"] == policy_id
    assert fetched["policy"]["version"] == 1
    versions = fetched["versions"]
    assert any(v.get("version") == 1 for v in versions)

    updated = client.put(
        f"/api/policies/{policy_id}",
        json=_base_policy(name="Updated", enabled=True, status="draft"),
    )
    assert updated.status_code == 200
    updated_policy = updated.get_json()["policy"]
    assert updated_policy["id"] == policy_id
    assert updated_policy["version"] == 2
    assert updated_policy["name"] == "Updated"
    assert updated_policy["enabled"] is True

    deleted = client.delete(f"/api/policies/{policy_id}")
    assert deleted.status_code == 200
    assert deleted.get_json()["ok"] is True
    not_found = client.get(f"/api/policies/{policy_id}")
    assert not_found.status_code == 404


def test_policy_validate_returns_errors(client):
    bad = _base_policy(name="", status="active", enabled=True)
    resp = client.post("/api/policies/validate", json=bad)
    assert resp.status_code == 200
    errors = resp.get_json()["errors"]
    assert any("name" in err for err in errors)
    assert any("active policy needs" in err for err in errors)


def test_auto_execute_gated_by_autonomy(client):
    policy = _base_policy(
        name="Auto execute cooling off",
        status="active",
        enabled=True,
        mode="AUTO_EXECUTE",
        priority=1,
        scope={"type": "nodes", "nodeIds": ["S1"]},
        conditions={
            "op": "AND",
            "items": [{"metric": "temp", "op": ">", "value": -1, "durationSec": 0}],
        },
        actions=[
            {"type": "disableCooling", "capability": "simulation", "availability": "available"}
        ],
        guardrails={"cooldownSec": 0, "maxPerHour": 100, "requireApproval": False},
    )
    created = client.post("/api/policies", json=policy).get_json()["policy"]
    assert created["mode"] == "AUTO_EXECUTE"
    policy_id = created["id"]

    client.post("/api/tick", json={"steps": 6})
    state = client.get("/api/state").get_json()
    assert state["tick"] == 6
    assert state["servers"]["S1"]["status"] == "running"
    assert state["servers"]["S1"]["cooling"] is True
    ops_before = client.get("/api/operations").get_json()["operations"]
    assert not any(op.get("policyId") == policy_id for op in ops_before)

    client.post("/api/autonomy", json={"enabled": True})
    client.post("/api/tick", json={"steps": 1})
    state2 = client.get("/api/state").get_json()
    assert state2["servers"]["S1"]["cooling"] is False
    ops_after = client.get("/api/operations").get_json()["operations"]
    assert any(op.get("policyId") == policy_id for op in ops_after)


def test_reset_preserves_policies_and_operations(client):
    policy = _base_policy(
        name="Runtime policy",
        status="active",
        enabled=True,
        mode="ADVISE_ONLY",
        scope={"type": "nodes", "nodeIds": ["S1"]},
        conditions={
            "op": "AND",
            "items": [{"metric": "temp", "op": ">", "value": -1, "durationSec": 0}],
        },
        actions=[
            {"type": "throttle", "capability": "simulation", "availability": "available"}
        ],
        guardrails={"cooldownSec": 0, "maxPerHour": 100, "requireApproval": False},
    )
    created = client.post("/api/policies", json=policy).get_json()["policy"]
    policy_id = created["id"]

    op = client.post(
        "/api/operations", json={"action": "enableCooling", "targets": ["S1"]}
    ).get_json()["operation"]
    op_id = op["id"]

    client.post("/api/reset", json={"reset_events": True})

    fetched = client.get(f"/api/policies/{policy_id}")
    assert fetched.status_code == 200
    ops = client.get("/api/operations").get_json()["operations"]
    assert any(entry.get("id") == op_id for entry in ops)


def test_duration_blocks_until_satisfied(client):
    policy = _base_policy(
        name="Duration policy",
        status="active",
        enabled=True,
        mode="ADVISE_ONLY",
        scope={"type": "nodes", "nodeIds": ["S1"]},
        conditions={
            "op": "AND",
            "items": [{"metric": "load", "op": ">", "value": -1, "durationSec": 3}],
        },
        actions=[
            {"type": "throttle", "capability": "simulation", "availability": "available"}
        ],
        guardrails={"cooldownSec": 0, "maxPerHour": 100, "requireApproval": False},
    )
    created = client.post("/api/policies", json=policy).get_json()["policy"]
    policy_id = created["id"]

    client.post("/api/tick", json={"steps": 6})
    client.post("/api/tick", json={"steps": 2})
    events2 = client.get("/api/events").get_json()["events"]
    assert any(
        e["type"] == "policy"
        and (e.get("payload") or {}).get("policy_id") == policy_id
        and (e.get("payload") or {}).get("decision") == "suggested"
        for e in events2
    )
