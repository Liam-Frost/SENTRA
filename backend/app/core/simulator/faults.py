from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

FAULT_CONFIG = {
    "overheat": {"duration": 10, "temp_delta": 3.0},
    "hardware_fail": {"duration": 15, "error_rate_delta": 2.0},
    "network_spike": {"duration": 5, "load_delta": 30.0},
}

VALID_FAULTS = tuple(FAULT_CONFIG.keys())


@dataclass
class Fault:
    fault_type: str
    target: str
    remaining_ticks: int
    start_tick: int

    def to_dict(self) -> dict:
        return {
            "type": self.fault_type,
            "target": self.target,
            "remaining_ticks": self.remaining_ticks,
            "start_tick": self.start_tick,
        }


class FaultManager:
    def __init__(self, durations: Optional[Dict[str, int]] = None) -> None:
        self._durations = durations or {}
        self.active_faults: List[Fault] = []

    def inject_fault(self, fault_type: str, target: str, current_tick: int) -> Fault:
        if fault_type not in FAULT_CONFIG:
            raise ValueError(f"Unknown fault type: {fault_type}")
        duration_override = self._durations.get(fault_type)
        if duration_override is None:
            duration_value = FAULT_CONFIG[fault_type]["duration"]
        else:
            duration_value = duration_override
        duration = max(1, int(duration_value))
        fault = Fault(
            fault_type=fault_type,
            target=target,
            remaining_ticks=duration,
            start_tick=current_tick,
        )
        self.active_faults.append(fault)
        return fault

    def apply_tick_effects(self) -> Dict[str, Dict[str, float]]:
        effects: Dict[str, Dict[str, float]] = {}
        remaining: List[Fault] = []
        for fault in self.active_faults:
            config = FAULT_CONFIG[fault.fault_type]
            entry = effects.setdefault(
                fault.target, {"load": 0.0, "temp": 0.0, "error_rate": 0.0}
            )
            entry["load"] += config.get("load_delta", 0.0)
            entry["temp"] += config.get("temp_delta", 0.0)
            entry["error_rate"] += config.get("error_rate_delta", 0.0)

            fault.remaining_ticks -= 1
            if fault.remaining_ticks > 0:
                remaining.append(fault)
        self.active_faults = remaining
        return effects

    def clear_faults(
        self, target: Optional[str] = None, fault_types: Optional[Iterable[str]] = None
    ) -> None:
        if target is None and fault_types is None:
            self.active_faults = []
            return

        fault_type_set = set(fault_types or [])
        remaining: List[Fault] = []
        for fault in self.active_faults:
            if target is not None and fault.target != target:
                remaining.append(fault)
                continue
            if fault_type_set and fault.fault_type not in fault_type_set:
                remaining.append(fault)
        self.active_faults = remaining


def _self_test() -> None:
    fm = FaultManager()
    fm.inject_fault("overheat", "S1", 0)
    fm.inject_fault("hardware_fail", "S2", 0)
    fm.inject_fault("network_spike", "S3", 0)
    assert len(fm.active_faults) == 3

    effects = fm.apply_tick_effects()
    assert effects["S1"]["temp"] == 3.0
    assert effects["S2"]["error_rate"] == 2.0
    assert effects["S3"]["load"] == 30.0

    for _ in range(9):
        fm.apply_tick_effects()
    assert all(f.fault_type != "overheat" for f in fm.active_faults)

    fm.clear_faults(target="S2", fault_types={"hardware_fail"})
    assert all(
        not (f.target == "S2" and f.fault_type == "hardware_fail")
        for f in fm.active_faults
    )


if __name__ == "__main__":
    _self_test()
    print("faults.py self-test OK")
