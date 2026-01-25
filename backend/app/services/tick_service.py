from __future__ import annotations

from typing import Dict, Optional

from app.core.simulator.faults import VALID_FAULTS
from app.core.simulator.world import SERVER_IDS, World
from app.services import autonomy_service, event_service

_WORLD: Optional[World] = None


def get_state() -> Dict[str, object]:
    world = _ensure_world()
    world.set_autonomy(autonomy_service.is_autonomy_enabled())
    return world.get_state()


def get_tick() -> int:
    world = _ensure_world()
    return int(world.tick_count)


def advance(steps: int = 1) -> Dict[str, object]:
    world = _ensure_world()
    for _ in range(int(steps)):
        world.tick(1)
        state = world.get_state()
        autonomy_service.on_tick(state, execute_action_fn=_execute_action)
    world.set_autonomy(autonomy_service.is_autonomy_enabled())
    return world.get_state()


def inject_fault(fault_type: str, target: str) -> None:
    if fault_type not in VALID_FAULTS:
        raise ValueError("invalid fault type")
    if target not in SERVER_IDS:
        raise ValueError("invalid target")
    world = _ensure_world()
    world.inject_fault(fault_type, target)
    event_service.append_event(
        tick=int(world.tick_count),
        event_type="fault",
        message=f"fault {fault_type} injected on {target}",
        payload={"type": fault_type, "target": target},
    )


def reset(reset_events: bool = True) -> Dict[str, object]:
    world = _ensure_world()
    world.reset()
    if autonomy_service.is_autonomy_enabled():
        autonomy_service.set_autonomy_enabled(False, tick=0)
    if reset_events:
        event_service.clear_events()
    else:
        event_service.append_event(
            tick=0,
            event_type="reset",
            message="world reset",
            payload={"reset_events": False},
        )
    return get_state()


def _execute_action(_world_state: Dict[str, object], action: str, target: Optional[str]):
    world = _ensure_world()
    world.apply_action(action, target)
    return world.get_state()


def _ensure_world() -> World:
    global _WORLD
    if _WORLD is None:
        _WORLD = World()
    return _WORLD
