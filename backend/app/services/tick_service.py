from __future__ import annotations

import threading
import time
from typing import Dict, Optional

from app.core.simulator.faults import VALID_FAULTS
from app.core.simulator.world import SERVER_IDS, World
from app.services import autonomy_service, event_service

_WORLD: Optional[World] = None
_WORLD_LOCK = threading.RLock()

_REALTIME_LOCK = threading.RLock()
_REALTIME_ENABLED = False
_REALTIME_HZ = 1.0
_REALTIME_THREAD: Optional[threading.Thread] = None
_REALTIME_STOP = threading.Event()


def get_state() -> Dict[str, object]:
    with _WORLD_LOCK:
        world = _ensure_world()
        world.set_autonomy(autonomy_service.is_autonomy_enabled())
        return world.get_state()


def get_tick() -> int:
    with _WORLD_LOCK:
        world = _ensure_world()
        return int(world.tick_count)


def advance(steps: int = 1) -> Dict[str, object]:
    with _WORLD_LOCK:
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
    with _WORLD_LOCK:
        world = _ensure_world()
        world.inject_fault(fault_type, target)
        event_service.append_event(
            tick=int(world.tick_count),
            event_type="fault",
            message=f"fault {fault_type} injected on {target}",
            payload={"type": fault_type, "target": target},
        )


def reset(reset_events: bool = True) -> Dict[str, object]:
    with _WORLD_LOCK:
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


def get_realtime_state() -> Dict[str, object]:
    with _REALTIME_LOCK:
        return {"enabled": _REALTIME_ENABLED, "hz": float(_REALTIME_HZ)}


def set_realtime(enabled: bool, hz: Optional[float] = None) -> Dict[str, object]:
    with _REALTIME_LOCK:
        if hz is not None:
            _set_realtime_hz(hz)
        if enabled:
            _start_realtime()
        else:
            _stop_realtime()
        return {"enabled": _REALTIME_ENABLED, "hz": float(_REALTIME_HZ)}


def _execute_action(_world_state: Dict[str, object], action: str, target: Optional[str]):
    with _WORLD_LOCK:
        world = _ensure_world()
        world.apply_action(action, target)
        return world.get_state()


def _ensure_world() -> World:
    global _WORLD
    if _WORLD is None:
        _WORLD = World()
    return _WORLD


def _set_realtime_hz(hz: float) -> None:
    global _REALTIME_HZ
    hz_value = float(hz)
    if hz_value <= 0:
        raise ValueError("hz must be > 0")
    _REALTIME_HZ = min(hz_value, 20.0)


def _start_realtime() -> None:
    global _REALTIME_ENABLED, _REALTIME_THREAD
    if _REALTIME_THREAD and _REALTIME_THREAD.is_alive():
        _REALTIME_ENABLED = True
        return
    _REALTIME_ENABLED = True
    _REALTIME_STOP.clear()
    _REALTIME_THREAD = threading.Thread(target=_realtime_loop, daemon=True)
    _REALTIME_THREAD.start()


def _stop_realtime() -> None:
    global _REALTIME_ENABLED
    _REALTIME_ENABLED = False
    _REALTIME_STOP.set()


def _realtime_loop() -> None:
    while True:
        if _REALTIME_STOP.is_set():
            break
        start = time.perf_counter()
        try:
            advance(1)
        except Exception:
            # avoid killing the thread if a single tick fails
            pass
        elapsed = time.perf_counter() - start
        interval = 1.0 / max(_REALTIME_HZ, 0.1)
        sleep_for = max(0.0, interval - elapsed)
        _REALTIME_STOP.wait(sleep_for)
