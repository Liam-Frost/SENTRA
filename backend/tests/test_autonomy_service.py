from app.persistence import db
from app.services import autonomy_service, event_service


def _ai_stub(*_args, **_kwargs):
    return {
        "root_causes": ["incident"],
        "recommended_actions": ["enableCooling"],
        "risks": ["risk"],
        "rollback_conditions": ["rollback"],
    }


def test_process_autonomy_blocks_restart_and_records_event(tmp_path):
    conn = db.connect(tmp_path / "events.sqlite3")
    db.init_db(conn)

    autonomy_service.set_autonomy_enabled(True, tick=1, conn=conn)
    autonomy_service._STATE.targets = {
        "S1": autonomy_service.TargetState(last_action="throttle", last_action_tick=0)
    }

    world_state = {
        "tick": 1,
        "incoming_traffic": 0,
        "servers": {
            "S1": {"temp": 90.0, "error_rate": 4.0, "health": 100, "cooling": True}
        },
        "autonomy_enabled": True,
    }

    autonomy_service.process_autonomy(world_state, ai_explainer_fn=_ai_stub, conn=conn)

    events = event_service.list_events(conn=conn)["events"]
    assert any(
        event["type"] == "action" and event["message"].startswith("blocked restart")
        for event in events
    )
    assert any(event["type"] == "ai" for event in events)
    assert autonomy_service._STATE.targets["S1"].last_action_tick == 1
