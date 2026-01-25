from __future__ import annotations

import os
import random
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
    AMBIENT_TEMP = rules.AMBIENT_TEMP
    BASELINE_ERROR_RATE = rules.BASELINE_ERROR_RATE
    BASELINE_TEMP = rules.BASELINE_TEMP
    ServerState = rules.ServerState
    apply_physics = rules.apply_physics
    compute_cooling_level = rules.compute_cooling_level
    compute_power = rules.compute_power
    clamp = rules.clamp
else:
    from .faults import FaultManager, VALID_FAULTS
    from .rules import (
        AMBIENT_TEMP,
        BASELINE_ERROR_RATE,
        BASELINE_TEMP,
        ServerState,
        apply_physics,
        compute_cooling_level,
        compute_power,
        clamp,
    )

SERVER_IDS = ("S1", "S2", "S3")

SIM_VERSION = "sim-2026-01-25"

MAX_TRAFFIC = 320.0
BASELINE_INCOMING_TRAFFIC = 70.0
TRAFFIC_PULL = 0.08
TRAFFIC_NOISE = 4.8
TRAFFIC_DRIFT_LIMIT = 22.0
TRAFFIC_BURST_CHANCE = 0.02
TRAFFIC_BURST_MIN = 18.0
TRAFFIC_BURST_MAX = 42.0
TRAFFIC_BURST_TICKS_MIN = 2
TRAFFIC_BURST_TICKS_MAX = 3

# Prevent cascading overload when capacity is reduced (e.g. thermal shutdown).
CAP_LOAD_PER_RUNNING_SERVER = 60.0
CAP_SLACK = 1.12

BOOT_DURATION = 6
RESTART_DURATION = 5
THERMAL_SHUTDOWN_TEMP = 88.0
THERMAL_RESTART_TEMP = 45.0
THERMAL_MIN_COOLDOWN = 6
BOOT_LOAD_TARGET = 70.0
BOOT_TEMP_DELTA = 1.2

HIGH_LOAD_THRESHOLD = 95.0
HIGH_LOAD_STRESS_BASE = 0.45
HIGH_LOAD_STRESS_MULT = 0.22
HIGH_LOAD_STRESS_DECAY = 0.6
HIGH_LOAD_STRESS_CAP = 10.0

LOAD_NOISE_STEP = 5.1
LOAD_NOISE_LIMIT = 12.75
LOAD_NOISE_DECAY = 0.85
TEMP_NOISE = 0.4
BACKGROUND_FAULT_CHANCE = 0.0064
BACKGROUND_FAULT_GAP = 25
THROTTLE_MIN_RATIO = 0.1
THROTTLE_MAX_EXTRA_RATIO = 0.2
THROTTLE_TEMP_THRESHOLD = 80.0
THROTTLE_TEMP_RANGE = 50.0
REROUTE_DELTA = 0.15
MIN_TRAFFIC_SHARE = 0.1


class World:
    def __init__(self, incoming_traffic: float = BASELINE_INCOMING_TRAFFIC) -> None:
        seed_raw = os.getenv("SENTRA_SIM_SEED")
        seed = int(seed_raw) if seed_raw and seed_raw.isdigit() else 7
        self._rng = random.Random(seed)
        self._traffic_drift = 0.0
        self._traffic_burst_ticks = 0
        self._traffic_burst_delta = 0.0
        self._load_noise = {server_id: 0.0 for server_id in SERVER_IDS}
        self._background_fault_gap = 0
        self.tick_count = 0
        self.autonomy_enabled = False
        self.incoming_traffic = clamp(incoming_traffic, 0.0, MAX_TRAFFIC)
        self.traffic_split = {server_id: 1.0 / len(SERVER_IDS) for server_id in SERVER_IDS}
        self.servers = {server_id: ServerState() for server_id in SERVER_IDS}
        for server in self.servers.values():
            self._set_booting(server, duration=BOOT_DURATION)
        self.faults = FaultManager()

    def reset(self) -> None:
        self.tick_count = 0
        self.autonomy_enabled = False
        self.incoming_traffic = BASELINE_INCOMING_TRAFFIC
        self.traffic_split = {server_id: 1.0 / len(SERVER_IDS) for server_id in SERVER_IDS}
        self.servers = {server_id: ServerState() for server_id in SERVER_IDS}
        for server in self.servers.values():
            self._set_booting(server, duration=BOOT_DURATION)
        self._traffic_drift = 0.0
        self._traffic_burst_ticks = 0
        self._traffic_burst_delta = 0.0
        self._load_noise = {server_id: 0.0 for server_id in SERVER_IDS}
        self._background_fault_gap = 0
        self.faults.clear_faults()

    def set_autonomy(self, enabled: bool) -> None:
        self.autonomy_enabled = bool(enabled)

    def set_incoming_traffic(self, value: float) -> None:
        self.incoming_traffic = clamp(float(value), 0.0, MAX_TRAFFIC)

    def get_state(self) -> dict:
        return {
            "sim_version": SIM_VERSION,
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
            server.cooling_level = compute_cooling_level(server.temp, True, server.status)
            server.power = compute_power(server.load, server.cooling_level, server.status)
            return
        if action == "disableCooling":
            target_id = self._require_target(action, target)
            server = self.servers[target_id]
            server.cooling = False
            server.cooling_level = 0.0
            server.power = compute_power(server.load, server.cooling_level, server.status)
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
        self._update_incoming_traffic()
        self._apply_capacity_cap()
        self._maybe_inject_background_fault()
        fault_effects = self.faults.apply_tick_effects()
        active_split = self._active_traffic_split()

        for server_id, server in self.servers.items():
            self._update_server_status(server)
            self._update_load_noise(server_id)
            effects = fault_effects.get(server_id, {})

            base_load = self._base_load_for(server_id, active_split)
            load_delta = effects.get("load", 0.0) + self._load_noise[server_id]
            temp_delta = effects.get("temp", 0.0) + self._rng.uniform(-TEMP_NOISE, TEMP_NOISE)
            error_rate_delta = effects.get("error_rate", 0.0)

            effective_load = clamp(base_load + load_delta, 0.0, 100.0)
            self._update_load_stress(server, effective_load)

            if server.status == "booting":
                base_load = BOOT_LOAD_TARGET
                temp_delta += BOOT_TEMP_DELTA
            elif server.status in {"thermal_shutdown", "off", "restarting"}:
                base_load = 0.0
                load_delta = 0.0
                temp_delta = 0.0
                error_rate_delta = 0.0

            apply_physics(
                server,
                base_load=base_load,
                load_stress=server.load_stress,
                load_delta=load_delta,
                temp_delta=temp_delta,
                error_rate_delta=error_rate_delta,
            )

            if server.status == "running" and server.temp >= THERMAL_SHUTDOWN_TEMP:
                self._enter_thermal_shutdown(server)
        self.tick_count += 1

    def _base_load_for(self, server_id: str, active_split: dict[str, float]) -> float:
        share = active_split.get(server_id, 0.0)
        return self.incoming_traffic * share

    def _restart_server(self, server_id: str) -> None:
        server = self.servers[server_id]
        server.temp = max(AMBIENT_TEMP + 5.0, server.temp - 10.0)
        server.error_rate = BASELINE_ERROR_RATE
        self._set_booting(
            server, duration=RESTART_DURATION, reset_error_rate=True, status="restarting"
        )
        self.faults.clear_faults(target=server_id, fault_types={"hardware_fail"})

    def _set_booting(
        self,
        server,
        duration: int,
        reset_error_rate: bool = False,
        status: str = "booting",
    ) -> None:
        server.status = status
        server.transition_ticks = max(1, int(duration))
        server.cooling = True
        if reset_error_rate:
            server.error_rate = BASELINE_ERROR_RATE

    def _enter_thermal_shutdown(self, server) -> None:
        server.status = "thermal_shutdown"
        server.transition_ticks = THERMAL_MIN_COOLDOWN
        server.cooling = True

    def _update_server_status(self, server) -> None:
        if server.status in {"booting", "restarting"}:
            if server.transition_ticks > 0:
                server.transition_ticks -= 1
            if server.transition_ticks <= 0:
                server.status = "running"
            return

        if server.status == "thermal_shutdown":
            if server.transition_ticks > 0:
                server.transition_ticks -= 1
            if server.transition_ticks <= 0 and server.temp <= THERMAL_RESTART_TEMP:
                self._set_booting(server, duration=BOOT_DURATION, reset_error_rate=True)

    def _active_traffic_split(self) -> dict[str, float]:
        active_servers = [
            server_id
            for server_id, server in self.servers.items()
            if server.status == "running"
        ]
        if not active_servers:
            return {server_id: 0.0 for server_id in self.servers}

        total = sum(self.traffic_split.get(server_id, 0.0) for server_id in active_servers)
        if total <= 0:
            share = 1.0 / len(active_servers)
            return {
                server_id: (share if server_id in active_servers else 0.0)
                for server_id in self.servers
            }

        return {
            server_id: (self.traffic_split.get(server_id, 0.0) / total)
            if server_id in active_servers
            else 0.0
            for server_id in self.servers
        }

    def _apply_capacity_cap(self) -> None:
        running = sum(1 for server in self.servers.values() if server.status == "running")
        if running <= 0:
            return
        cap = CAP_LOAD_PER_RUNNING_SERVER * running
        hard_cap = cap * CAP_SLACK
        if self.incoming_traffic <= hard_cap:
            return
        # Reduce quickly, but keep some inertia.
        excess = self.incoming_traffic - hard_cap
        self.incoming_traffic = hard_cap + excess * 0.15
        self._traffic_drift = min(self._traffic_drift, 0.0)

    def _update_incoming_traffic(self) -> None:
        drift_step = self._rng.uniform(-4.0, 4.0)
        self._traffic_drift = clamp(
            self._traffic_drift + drift_step, -TRAFFIC_DRIFT_LIMIT, TRAFFIC_DRIFT_LIMIT
        )
        target = BASELINE_INCOMING_TRAFFIC + self._traffic_drift
        noise = self._rng.uniform(-TRAFFIC_NOISE, TRAFFIC_NOISE)

        if self._traffic_burst_ticks <= 0 and self._rng.random() < TRAFFIC_BURST_CHANCE:
            self._traffic_burst_ticks = self._rng.randint(
                TRAFFIC_BURST_TICKS_MIN, TRAFFIC_BURST_TICKS_MAX
            )
            self._traffic_burst_delta = self._rng.uniform(TRAFFIC_BURST_MIN, TRAFFIC_BURST_MAX)

        burst = 0.0
        if self._traffic_burst_ticks > 0:
            burst = self._traffic_burst_delta
            self._traffic_burst_ticks -= 1
            if self._traffic_burst_ticks <= 0:
                self._traffic_burst_delta = 0.0

        self.incoming_traffic += (target - self.incoming_traffic) * TRAFFIC_PULL + noise + burst
        self.incoming_traffic = clamp(self.incoming_traffic, 0.0, MAX_TRAFFIC)

    def _update_load_noise(self, server_id: str) -> None:
        current = self._load_noise.get(server_id, 0.0)
        current += self._rng.uniform(-LOAD_NOISE_STEP, LOAD_NOISE_STEP)
        current *= LOAD_NOISE_DECAY
        self._load_noise[server_id] = clamp(current, -LOAD_NOISE_LIMIT, LOAD_NOISE_LIMIT)

    def _update_load_stress(self, server, load: float) -> None:
        if server.status != "running":
            server.load_stress = max(0.0, server.load_stress - HIGH_LOAD_STRESS_DECAY * 1.5)
            return
        if load >= HIGH_LOAD_THRESHOLD:
            increment = HIGH_LOAD_STRESS_BASE + server.load_stress * HIGH_LOAD_STRESS_MULT
            server.load_stress = min(HIGH_LOAD_STRESS_CAP, server.load_stress + increment)
            return
        server.load_stress = max(0.0, server.load_stress - HIGH_LOAD_STRESS_DECAY)

    def _maybe_inject_background_fault(self) -> None:
        if self._background_fault_gap > 0:
            self._background_fault_gap -= 1
            return
        if self._rng.random() > BACKGROUND_FAULT_CHANCE:
            return
        active_targets = [
            server_id
            for server_id, server in self.servers.items()
            if server.status == "running"
        ]
        if not active_targets:
            return
        fault_type = self._rng.choice(VALID_FAULTS)
        target = self._rng.choice(active_targets)
        self.faults.inject_fault(fault_type, target, self.tick_count)
        self._background_fault_gap = BACKGROUND_FAULT_GAP

    def _reroute_from(self, target: str) -> None:
        current_share = self.traffic_split.get(target, 0.0)
        reduction = min(REROUTE_DELTA, max(0.0, current_share - MIN_TRAFFIC_SHARE))
        if reduction <= 0.0:
            return

        self.traffic_split[target] = current_share - reduction
        other_ids = [
            server_id
            for server_id in SERVER_IDS
            if server_id != target and self.servers[server_id].status == "running"
        ]
        if not other_ids:
            return

        weights = {}
        for server_id in other_ids:
            load_ratio = clamp(self.servers[server_id].load / 100.0, 0.0, 1.0)
            weights[server_id] = max(0.1, 1.05 - load_ratio)
        total_weight = sum(weights.values())
        for server_id in other_ids:
            share = reduction * (weights[server_id] / total_weight)
            self.traffic_split[server_id] += share
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
    w.tick(BOOT_DURATION + 1)
    state = w.get_state()
    assert state["tick"] == BOOT_DURATION + 1
    for server_id in SERVER_IDS:
        assert state["servers"][server_id]["load"] >= 0.0

    w.inject_fault("overheat", "S1")
    temp_before = w.servers["S1"].temp
    w.tick(1)
    assert w.servers["S1"].temp > temp_before

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
