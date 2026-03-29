"""Tests for Actions API endpoints."""


def test_list_actions_returns_default_actions(client):
    """Test that GET /api/actions returns the 14 default system actions."""
    resp = client.get("/api/actions")
    assert resp.status_code == 200
    
    data = resp.get_json()
    assert "actions" in data
    actions = data["actions"]
    
    # Should have 14 default system actions
    assert len(actions) >= 14
    
    # Check that key actions exist
    action_ids = [a["id"] for a in actions]
    assert "enableCooling" in action_ids
    assert "disableCooling" in action_ids
    assert "throttle" in action_ids
    assert "restart" in action_ids
    
    # Check structure of first action
    first = actions[0]
    assert "id" in first
    assert "label" in first
    assert "capability" in first
    assert "availability" in first
    assert "risk_level" in first
    assert "requires_target" in first
    assert "is_system" in first


def test_list_actions_filter_by_availability(client):
    """Test filtering actions by availability."""
    resp = client.get("/api/actions?availability=available")
    assert resp.status_code == 200
    
    data = resp.get_json()
    actions = data["actions"]
    
    # All returned actions should have availability="available"
    for action in actions:
        assert action["availability"] == "available"


def test_list_actions_filter_by_capability(client):
    """Test filtering actions by capability."""
    resp = client.get("/api/actions?capability=simulation")
    assert resp.status_code == 200
    
    data = resp.get_json()
    actions = data["actions"]
    
    # All returned actions should have capability="simulation"
    for action in actions:
        assert action["capability"] == "simulation"


def test_get_action_by_id(client):
    """Test GET /api/actions/<id>."""
    resp = client.get("/api/actions/enableCooling")
    assert resp.status_code == 200
    
    data = resp.get_json()
    assert "action" in data
    action = data["action"]
    
    assert action["id"] == "enableCooling"
    assert action["label"] == "Enable cooling"
    assert action["capability"] == "simulation"
    assert action["availability"] == "available"
    assert action["risk_level"] == 0
    assert action["requires_target"] is True
    assert action["is_system"] is True


def test_get_action_not_found(client):
    """Test GET /api/actions/<id> with non-existent ID."""
    resp = client.get("/api/actions/nonexistent")
    assert resp.status_code == 404


def test_create_custom_action(client):
    """Test POST /api/actions to create a custom action."""
    new_action = {
        "id": "custom_health_check",
        "label": "Custom Health Check",
        "category": "diagnostics",
        "capability": "probe",
        "availability": "available",
        "risk_level": 1,
        "requires_target": True,
        "description": "Custom health check action",
    }
    
    resp = client.post("/api/actions", json=new_action)
    assert resp.status_code == 200
    
    data = resp.get_json()
    assert "action" in data
    action = data["action"]
    
    assert action["id"] == "custom_health_check"
    assert action["label"] == "Custom Health Check"
    assert action["is_system"] == False  # Changed from 'is False' to '== False' to handle int/bool comparison
    
    # Verify we can retrieve it
    resp2 = client.get("/api/actions/custom_health_check")
    assert resp2.status_code == 200


def test_create_action_validates_id(client):
    """Test that action IDs are validated."""
    # Invalid ID (spaces not allowed)
    bad_action = {
        "id": "invalid id with spaces",
        "label": "Bad Action",
        "capability": "probe",
        "availability": "available",
        "risk_level": 1,
    }
    
    resp = client.post("/api/actions", json=bad_action)
    assert resp.status_code == 400


def test_create_action_duplicate_id(client):
    """Test that duplicate IDs are rejected."""
    action = {
        "id": "test_duplicate",
        "label": "Test Action",
        "capability": "probe",
        "availability": "available",
        "risk_level": 1,
    }
    
    # First creation should succeed
    resp1 = client.post("/api/actions", json=action)
    assert resp1.status_code == 200
    
    # Second creation with same ID should fail
    resp2 = client.post("/api/actions", json=action)
    assert resp2.status_code == 400


def test_update_custom_action(client):
    """Test PUT /api/actions/<id> to update a custom action."""
    # Create a custom action first
    action = {
        "id": "test_update",
        "label": "Original Label",
        "capability": "probe",
        "availability": "available",
        "risk_level": 1,
    }
    client.post("/api/actions", json=action)
    
    # Update it
    update = {"label": "Updated Label", "description": "New description"}
    resp = client.put("/api/actions/test_update", json=update)
    assert resp.status_code == 200
    
    data = resp.get_json()
    action = data["action"]
    assert action["label"] == "Updated Label"
    assert action["description"] == "New description"


def test_update_system_action_only_label_description(client):
    """Test that system actions can only update label and description."""
    # Try to update capability of a system action
    update = {"capability": "both", "risk_level": 3}
    resp = client.put("/api/actions/enableCooling", json=update)
    assert resp.status_code == 400
    
    # But updating label/description should work
    update2 = {"label": "Custom Label", "description": "Custom description"}
    resp2 = client.put("/api/actions/enableCooling", json=update2)
    assert resp2.status_code == 200


def test_delete_custom_action(client):
    """Test DELETE /api/actions/<id> for custom actions."""
    # Create a custom action
    action = {
        "id": "test_delete",
        "label": "Delete Me",
        "capability": "probe",
        "availability": "available",
        "risk_level": 1,
    }
    client.post("/api/actions", json=action)
    
    # Delete it
    resp = client.delete("/api/actions/test_delete")
    assert resp.status_code == 200
    
    # Verify it's gone
    resp2 = client.get("/api/actions/test_delete")
    assert resp2.status_code == 404


def test_delete_system_action_fails(client):
    """Test that system actions cannot be deleted."""
    resp = client.delete("/api/actions/enableCooling")
    assert resp.status_code == 400


def test_execute_actions(client):
    """Test POST /api/actions/execute to create operations."""
    body = {
        "actions": ["restart", "health_check"],
        "targets": ["S1", "S2"],
        "initiator": "bulk",
    }
    
    resp = client.post("/api/actions/execute", json=body)
    assert resp.status_code == 200
    
    data = resp.get_json()
    assert "operations" in data
    operations = data["operations"]
    
    # Should create 2 operations (one per action)
    assert len(operations) == 2
    
    # Verify operations were created
    for op_id in operations:
        op_resp = client.get(f"/api/operations/{op_id}")
        assert op_resp.status_code == 200


def test_get_action_references(client):
    """Test GET /api/actions/<id>/references."""
    # Create a policy that uses an action
    policy = {
        "name": "Test Policy",
        "status": "active",
        "enabled": True,
        "mode": "ADVISE_ONLY",
        "priority": 100,
        "scope": {"type": "all"},
        "conditions": {
            "op": "AND",
            "items": [{"metric": "temp", "op": ">", "value": 80}],
        },
        "actions": [
            {"type": "restart", "capability": "simulation", "availability": "available"}
        ],
        "guardrails": {"cooldownSec": 60, "maxPerHour": 10, "requireApproval": False},
    }
    client.post("/api/policies", json=policy)
    
    # Get references for the restart action
    resp = client.get("/api/actions/restart/references")
    assert resp.status_code == 200
    
    data = resp.get_json()
    assert "policies" in data
    assert "operations" in data
    
    # Should have at least 1 policy reference
    assert len(data["policies"]) >= 1


def test_create_action_with_parameters_schema(client):
    """Test creating an action with a parameters schema."""
    action = {
        "id": "test_params",
        "label": "Test with Params",
        "capability": "probe",
        "availability": "available",
        "risk_level": 2,
        "parameters_schema": '{"type": "object", "properties": {"timeout": {"type": "number"}}}',
    }
    
    resp = client.post("/api/actions", json=action)
    assert resp.status_code == 200
    
    data = resp.get_json()
    action_data = data["action"]
    assert action_data["parameters_schema"] is not None
