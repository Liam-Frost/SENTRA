from app.core import controller


def test_detect_incidents_thresholds():
    world_state = {
        "servers": {
            "S1": {"temp": 81.0, "error_rate": 6.0, "health": 50, "cooling": False}
        }
    }

    incidents = controller.detect_incidents(world_state)
    metrics = {(incident["metric"], incident["target"]) for incident in incidents}

    assert ("temp", "S1") in metrics
    assert ("error_rate", "S1") in metrics
    assert ("health", "S1") in metrics

    temp_incident = next(i for i in incidents if i["metric"] == "temp")
    assert temp_incident["threshold"] == 80.0


def test_select_action_priority_and_restart_gate():
    world_state = {
        "servers": {
            "S1": {"temp": 81.0, "error_rate": 6.0, "health": 100, "cooling": False}
        }
    }
    incident = controller.detect_incidents(world_state)[0]
    decision = controller.select_action(world_state, incident)
    assert decision["action"] == "enableCooling"
    assert decision["blocked"] is False

    restart_unsafe_state = {
        "servers": {
            "S1": {"temp": 90.0, "error_rate": 4.0, "health": 100, "cooling": True}
        }
    }
    incident = controller.detect_incidents(restart_unsafe_state)[0]
    decision = controller.select_action(restart_unsafe_state, incident, last_action="throttle")
    assert decision["action"] == "restart"
    assert decision["blocked"] is True

    restart_safe_state = {
        "servers": {
            "S1": {"temp": 80.0, "error_rate": 6.0, "health": 100, "cooling": True}
        }
    }
    incident = controller.detect_incidents(restart_safe_state)[0]
    decision = controller.select_action(restart_safe_state, incident, last_action="throttle")
    assert decision["action"] == "restart"
    assert decision["blocked"] is False
