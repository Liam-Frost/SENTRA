import os
import sys
from typing import Dict, Optional

if __name__ == "__main__" and __package__ is None:
    import importlib

    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, "../../../.."))
    sys.path.insert(0, repo_root)

    faults = importlib.import_module("backend.app.core.simulator.faults")
    rules = importlib.import_module("backend.app.core.simulator.rules")

    FaultManager = faults.FaultManager
    VALID_FAULTS = faults.VALID_FAULTS
    BASELINE_ERROR_RATE = rules.BASELINE_ERROR_RATE
    BASELINE_TEMP = rules.BASELINE_TEMP
    ServerState = rules.ServerState
    apply_physics = rules.apply_physics
    compute_power = rules.compute_power
    clamp = rules.clamp
else:
    from .faults import FaultManager, VALID_FAULTS
    from .rules import (
        BASELINE_ERROR_RATE,
        BASELINE_TEMP,
        ServerState,
        apply_physics,
        compute_power,
        clamp,
    )

SERVER_IDS = ("S1", "S2", "S3")

MAX_TRAFFIC = 300.0
BASELINE_INCOMING_TRAFFIC = 0.0
THROTTLE_MIN_RATIO = 0.1
THROTTLE_MAX_EXTRA_RATIO = 0.2
THROTTLE_TEMP_THRESHOLD = 80.0
THROTTLE_TEMP_RANGE = 50.0
REROUTE_DELTA = 0.15
MIN_TRAFFIC_SHARE = 0.1


class World:
    def __init__(self, incoming_traffic: float = BASELINE_INCOMING_TRAFFIC) -> None:
        self.tick_count = 0
        self.autonomy_enabled = False
        self.incoming_traffic = clamp(incoming_traffic, 0.0, MAX_TRAFFIC)
        self.traffic_split = {server_id: 1.0 / len(SERVER_IDS) for server_id in SERVER_IDS}
        self.servers = {server_id: ServerState() for server_id in SERVER_IDS}
        self.faults = FaultManager()

    def reset(self) -> None:
        self.tick_count = 0
        self.autonomy_enabled = False
        self.incoming_traffic = BASELINE_INCOMING_TRAFFIC
        self.traffic_split = {server_id: 1.0 / len(SERVER_IDS) for server_id in SERVER_IDS}
        self.servers = {server_id: ServerState() for server_id in SERVER_IDS}
        self.faults.clear_faults()

    def set_autonomy(self, enabled: bool) -> None:
        self.autonomy_enabled = bool(enabled)

    def set_incoming_traffic(self, value: float) -> None:
        self.incoming_traffic = clamp(float(value), 0.0, MAX_TRAFFIC)

    def get_state(self) -> dict:
        return {
            "tick": int(self.tick_count),
            "incoming_traffic": round(self.incoming_traffic, 2),
            "servers": {server_id: state.to_dict() for server_id, state in self.servers.items()},
            "autonomy_enabled": bool(self.autonomy_enabled),
        }

    def tick(self, steps: int = 1) -> dict:
        if steps < 1:
            raise ValueError("steps must be >= 1")
        for _ in range(int(steps)):
            self._tick_once()
        return self.get_state()

    def inject_fault(self, fault_type: str, target: str) -> None:
        if fault_type not in VALID_FAULTS:
            raise ValueError(f"Unknown fault type: {fault_type}")
        if target not in self.servers:
            raise ValueError(f"Unknown server id: {target}")
        self.faults.inject_fault(fault_type, target, self.tick_count)

    def apply_action(self, action: str, target: Optional[str] = None) -> None:
        if action == "enableCooling":
            target_id = self._require_target(action, target)
            server = self.servers[target_id]
            server.cooling = True
            server.power = compute_power(server.load, server.cooling)
            return
        if action == "disableCooling":
            target_id = self._require_target(action, target)
            server = self.servers[target_id]
            server.cooling = False
            server.power = compute_power(server.load, server.cooling)
            return
        if action == "restart":
            target_id = self._require_target(action, target)
            self._restart_server(target_id)
            return
        if action == "reroute":
            target_id = self._require_target(action, target)
            self._reroute_from(target_id)
            return
        if action == "throttle":
            ratio = self._calculate_throttle_ratio()
            self.incoming_traffic = clamp(
                self.incoming_traffic * (1.0 - ratio), 0.0, MAX_TRAFFIC
            )
            return
        raise ValueError(f"Unknown action: {action}")

    def _tick_once(self) -> None:
        fault_effects = self.faults.apply_tick_effects()
        for server_id, server in self.servers.items():
            server.load = self._base_load_for(server_id)
            effects = fault_effects.get(server_id, {})
            apply_physics(
                server,
                load_delta=effects.get("load", 0.0),
                temp_delta=effects.get("temp", 0.0),
                error_rate_delta=effects.get("error_rate", 0.0),
            )
        self.tick_count += 1

    def _base_load_for(self, server_id: str) -> float:
        share = self.traffic_split.get(server_id, 0.0)
        return self.incoming_traffic * share

    def _restart_server(self, server_id: str) -> None:
        server = self.servers[server_id]
        server.temp = BASELINE_TEMP
        server.error_rate = BASELINE_ERROR_RATE
        self.faults.clear_faults(target=server_id, fault_types={"hardware_fail"})

    def _reroute_from(self, target: str) -> None:
        current_share = self.traffic_split.get(target, 0.0)
        reduction = min(REROUTE_DELTA, max(0.0, current_share - MIN_TRAFFIC_SHARE))
        if reduction <= 0.0:
            return

        self.traffic_split[target] = current_share - reduction
        other_ids = [server_id for server_id in SERVER_IDS if server_id != target]
        increment = reduction / len(other_ids)
        for server_id in other_ids:
            self.traffic_split[server_id] += increment
        self._normalize_split()

    def _normalize_split(self) -> None:
        total = sum(self.traffic_split.values())
        if total <= 0:
            self.traffic_split = {server_id: 1.0 / len(SERVER_IDS) for server_id in SERVER_IDS}
            return
        for server_id in self.traffic_split:
            self.traffic_split[server_id] = self.traffic_split[server_id] / total

    def _calculate_throttle_ratio(self) -> float:
        max_temp = max(server.temp for server in self.servers.values())
        if max_temp <= THROTTLE_TEMP_THRESHOLD:
            return THROTTLE_MIN_RATIO
        extra = min(
            THROTTLE_MAX_EXTRA_RATIO,
            (max_temp - THROTTLE_TEMP_THRESHOLD) / THROTTLE_TEMP_RANGE,
        )
        return THROTTLE_MIN_RATIO + extra

    def _require_target(self, action: str, target: Optional[str]) -> str:
        if target is None:
            raise ValueError(f"Action {action} requires a target")
        if target not in self.servers:
            raise ValueError(f"Unknown server id: {target}")
        return target


def _self_test() -> None:
    w = World(incoming_traffic=300)
    w.tick(1)
    state = w.get_state()
    assert state["tick"] == 1
    for server_id in SERVER_IDS:
        assert abs(state["servers"][server_id]["load"] - 100.0) < 1e-6

    w.inject_fault("overheat", "S1")
    temp_before = w.servers["S1"].temp
    w.tick(1)
    assert w.servers["S1"].temp > temp_before + 2.0

    w.apply_action("enableCooling", "S1")
    assert w.servers["S1"].cooling is True

    load_before = w.get_state()["servers"]["S1"]["load"]
    w.apply_action("reroute", "S1")
    w.tick(1)
    load_after = w.get_state()["servers"]["S1"]["load"]
    assert load_after < load_before

    traffic_before = w.incoming_traffic
    w.apply_action("throttle")
    assert w.incoming_traffic < traffic_before

    w.inject_fault("hardware_fail", "S2")
    w.tick(1)
    w.apply_action("restart", "S2")
    assert w.servers["S2"].error_rate == 0.0


if __name__ == "__main__":
    _self_test()
    print("world.py self-test OK")
