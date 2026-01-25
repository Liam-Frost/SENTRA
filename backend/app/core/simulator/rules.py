from dataclasses import dataclass

AMBIENT_TEMP = 25.0
TEMP_MAX = 110.0
BASE_HEAT = 0.6
TEMP_LOAD_FACTOR = 0.04
LOAD_HEAT_CURVE = 1.1
LOAD_STRESS_HEAT = 1.2
RUNAWAY_TEMP_THRESHOLD = 90.0
RUNAWAY_HEAT_FACTOR = 0.08
RUNAWAY_HEAT_EXP = 1.4
PASSIVE_COOLING = 0.04
COOLING_EFFECT_MAX = 3.2

ERROR_TEMP_THRESHOLD = 70.0
ERROR_RATE_TEMP_FACTOR = 0.012
ERROR_RATE_TEMP_EXP = 1.25
ERROR_RATE_DECAY = 0.92
HEALTH_TEMP_FACTOR = 0.18
HEALTH_ERROR_RATE_FACTOR = 0.45
HEALTH_RECOVERY = 0.15

POWER_BASE = 60.0
POWER_PER_LOAD = 1.7
POWER_COOLING_MAX = 80.0
POWER_BOOT_BOOST = 40.0
POWER_OFF = 12.0

BASELINE_TEMP = 36.0
BASELINE_ERROR_RATE = 0.0
BASELINE_HEALTH = 100.0
BASELINE_LOAD = 0.0
BASELINE_COOLING = True
BASELINE_STATUS = "booting"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class ServerState:
    load: float = BASELINE_LOAD
    temp: float = BASELINE_TEMP
    error_rate: float = BASELINE_ERROR_RATE
    power: float = POWER_BASE
    health: float = BASELINE_HEALTH
    cooling: bool = BASELINE_COOLING
    cooling_level: float = 0.0
    status: str = BASELINE_STATUS
    transition_ticks: int = 0
    load_stress: float = 0.0

    def to_dict(self) -> dict:
        return {
            "load": round(self.load, 2),
            "temp": round(self.temp, 2),
            "error_rate": round(self.error_rate, 2),
            "power": round(self.power, 2),
            "health": int(round(self.health)),
            "cooling": bool(self.cooling),
            "cooling_level": round(self.cooling_level, 2),
            "status": self.status,
        }


def compute_power(load: float, cooling_level: float, status: str) -> float:
    cooling_power = POWER_COOLING_MAX * clamp(cooling_level, 0.0, 1.0)
    if status in {"off", "thermal_shutdown"}:
        return POWER_OFF + cooling_power
    base = POWER_BASE + load * POWER_PER_LOAD
    if status in {"booting", "restarting"}:
        base += POWER_BOOT_BOOST
    return base + cooling_power


def compute_cooling_level(temp: float, enabled: bool, status: str) -> float:
    if status == "thermal_shutdown":
        return 1.0
    if not enabled:
        return 0.0
    if temp < 30:
        return 0.1
    if temp < 35:
        return 0.2
    if temp < 40:
        return 0.5
    if temp < 45:
        return 0.7
    if temp < 55:
        return 0.85
    if temp < 70:
        return 0.95
    return 1.0


def apply_physics(
    state: ServerState,
    base_load: float,
    load_stress: float = 0.0,
    load_delta: float = 0.0,
    temp_delta: float = 0.0,
    error_rate_delta: float = 0.0,
) -> None:
    state.load = clamp(base_load + load_delta, 0.0, 100.0)

    state.cooling_level = compute_cooling_level(state.temp, state.cooling, state.status)
    load_ratio = clamp(state.load / 100.0, 0.0, 1.0)
    stress = max(0.0, load_stress)
    if state.status in {"thermal_shutdown", "off", "restarting"}:
        # Power/load are stopped; cooling can still reduce temperature.
        stress = 0.0
        heat_gain = 0.0
    else:
        heat_gain = (
            BASE_HEAT
            + TEMP_LOAD_FACTOR * state.load
            + LOAD_HEAT_CURVE * (load_ratio**2)
            + LOAD_STRESS_HEAT * (stress**1.1)
        )
        # Thermal runaway only applies once we are already very hot.
        if state.temp > RUNAWAY_TEMP_THRESHOLD:
            heat_gain += RUNAWAY_HEAT_FACTOR * (
                (state.temp - RUNAWAY_TEMP_THRESHOLD) ** RUNAWAY_HEAT_EXP
            )
    passive_cooling = PASSIVE_COOLING * max(0.0, state.temp - AMBIENT_TEMP)
    active_cooling = COOLING_EFFECT_MAX * state.cooling_level

    state.temp += heat_gain - passive_cooling - active_cooling + temp_delta
    state.temp = clamp(state.temp, AMBIENT_TEMP, TEMP_MAX)

    if state.temp > ERROR_TEMP_THRESHOLD:
        severity = max(0.0, state.temp - ERROR_TEMP_THRESHOLD)
        state.error_rate += (severity**ERROR_RATE_TEMP_EXP) * ERROR_RATE_TEMP_FACTOR
    else:
        state.error_rate *= ERROR_RATE_DECAY
    state.error_rate += error_rate_delta

    state.health -= (
        max(0.0, state.temp - ERROR_TEMP_THRESHOLD) * HEALTH_TEMP_FACTOR
        + state.error_rate * HEALTH_ERROR_RATE_FACTOR
    )
    state.health += HEALTH_RECOVERY

    state.power = compute_power(state.load, state.cooling_level, state.status)

    state.load = clamp(state.load, 0.0, 100.0)
    state.temp = clamp(state.temp, AMBIENT_TEMP, TEMP_MAX)
    state.error_rate = clamp(state.error_rate, 0.0, 100.0)
    state.health = clamp(state.health, 0.0, 100.0)
    state.power = max(0.0, state.power)


def _self_test() -> None:
    base = ServerState(load=50.0, temp=40.0, error_rate=0.0, health=100.0, cooling=False)
    apply_physics(base, base_load=50.0)
    temp_no_cooling = base.temp
    power_no_cooling = base.power

    cool = ServerState(load=50.0, temp=40.0, error_rate=0.0, health=100.0, cooling=True)
    apply_physics(cool, base_load=50.0)
    temp_with_cooling = cool.temp
    power_with_cooling = cool.power

    assert temp_with_cooling < temp_no_cooling
    assert power_with_cooling > power_no_cooling

    hot = ServerState(load=90.0, temp=75.0, error_rate=0.0, health=100.0, cooling=False)
    apply_physics(hot, base_load=90.0)
    assert hot.error_rate > 0.0

    assert 0.0 <= hot.health <= 100.0
    assert 0.0 <= hot.error_rate <= 100.0


if __name__ == "__main__":
    _self_test()
    print("rules.py self-test OK")
