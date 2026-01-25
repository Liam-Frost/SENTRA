def test_get_state_shape(client):
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.get_json()
    assert "tick" in data
    assert "incoming_traffic" in data
    assert "servers" in data
    assert "autonomy_enabled" in data


def test_tick_validation(client):
    response = client.post("/api/tick", json={"steps": 0})
    assert response.status_code == 400
    data = response.get_json()
    assert data["error"]["code"] == "BAD_REQUEST"


def test_fault_injection_and_events(client):
    response = client.post("/api/fault", json={"type": "overheat", "target": "S1"})
    assert response.status_code == 200
    events = client.get("/api/events").get_json()["events"]
    assert any(
        event["type"] == "fault" and event["payload"]["type"] == "overheat"
        for event in events
    )


def test_autonomy_toggle(client):
    response = client.post("/api/autonomy", json={"enabled": True})
    assert response.status_code == 200
    data = response.get_json()
    assert data["enabled"] is True
    state = client.get("/api/state").get_json()
    assert state["autonomy_enabled"] is True


def test_reset_preserve_events_false(client):
    client.post("/api/fault", json={"type": "overheat", "target": "S1"})
    response = client.post("/api/reset", json={"reset_events": False})
    assert response.status_code == 200
    events = client.get("/api/events").get_json()["events"]
    assert any(event["type"] == "reset" for event in events)
