import pytest

from app.persistence import db
from app.services import event_service


def test_append_event_accepts_all_types(tmp_path):
    conn = db.connect(tmp_path / "events.sqlite3")
    db.init_db(conn)

    event_service.append_event(
        tick=1,
        event_type="fault",
        message="fault",
        payload={"type": "overheat", "target": "S1"},
        conn=conn,
    )
    event_service.append_event(
        tick=2,
        event_type="incident",
        message="incident",
        payload={"target": "S1", "metric": "temp", "value": 81.0, "threshold": 80.0},
        conn=conn,
    )
    event_service.append_event(
        tick=3,
        event_type="action",
        message="action",
        payload={"action": "enableCooling", "target": "S1"},
        conn=conn,
    )
    event_service.append_event(
        tick=4,
        event_type="ai",
        message="ai",
        payload={
            "root_causes": ["x"],
            "recommended_actions": ["y"],
            "risks": ["z"],
            "rollback_conditions": ["r"],
        },
        conn=conn,
    )
    event_service.append_event(
        tick=5,
        event_type="autonomy",
        message="autonomy",
        payload={"enabled": True},
        conn=conn,
    )
    event_service.append_event(
        tick=6,
        event_type="reset",
        message="reset",
        payload={"reset_events": False},
        conn=conn,
    )

    events = event_service.list_events(conn=conn)["events"]
    types = {event["type"] for event in events}
    assert types == {"fault", "incident", "action", "ai", "autonomy", "reset"}


def test_append_event_rejects_invalid_ai_payload(tmp_path):
    conn = db.connect(tmp_path / "events.sqlite3")
    db.init_db(conn)

    with pytest.raises(ValueError):
        event_service.append_event(
            tick=1,
            event_type="ai",
            message="ai",
            payload={"root_causes": []},
            conn=conn,
        )


def test_list_events_filters(tmp_path):
    conn = db.connect(tmp_path / "events.sqlite3")
    db.init_db(conn)

    event_service.append_event(
        tick=1,
        event_type="fault",
        message="fault",
        payload={"type": "overheat", "target": "S1"},
        conn=conn,
    )
    event_service.append_event(
        tick=2,
        event_type="incident",
        message="incident",
        payload={"target": "S2", "metric": "temp", "value": 81.0, "threshold": 80.0},
        conn=conn,
    )
    event_service.append_event(
        tick=3,
        event_type="action",
        message="action",
        payload={"action": "enableCooling", "target": "S2"},
        conn=conn,
    )

    since_events = event_service.list_events(since_tick=2, conn=conn)["events"]
    assert len(since_events) == 2

    fault_events = event_service.list_events(types=["fault"], conn=conn)["events"]
    assert len(fault_events) == 1
    assert fault_events[0]["type"] == "fault"

    target_events = event_service.list_events(targets=["S2"], conn=conn)["events"]
    assert len(target_events) == 2
