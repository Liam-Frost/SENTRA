from dataclasses import dataclass

TEMP_LOAD_FACTOR = 0.02
NATURAL_COOLING = 0.5
COOLING_EFFECT = 1.5
ERROR_TEMP_THRESHOLD = 70.0
ERROR_RATE_TEMP_FACTOR = 0.02
ERROR_RATE_DECAY = 0.95
HEALTH_TEMP_FACTOR = 0.2
HEALTH_ERROR_RATE_FACTOR = 0.5
HEALTH_RECOVERY = 0.2
POWER_BASE = 80.0
POWER_PER_LOAD = 2.0
POWER_COOLING_BONUS = 40.0

BASELINE_TEMP = 40.0
BASELINE_ERROR_RATE = 0.0
BASELINE_HEALTH = 100.0
BASELINE_LOAD = 0.0
BASELINE_COOLING = False


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

    def to_dict(self) -> dict:
        return {
            "load": round(self.load, 2),
            "temp": round(self.temp, 2),
            "error_rate": round(self.error_rate, 2),
            "power": round(self.power, 2),
            "health": int(round(self.health)),
            "cooling": bool(self.cooling),
        }


def compute_power(load: float, cooling: bool) -> float:
    return POWER_BASE + load * POWER_PER_LOAD + (POWER_COOLING_BONUS if cooling else 0.0)


def apply_physics(
    state: ServerState,
    load_delta: float = 0.0,
    temp_delta: float = 0.0,
    error_rate_delta: float = 0.0,
) -> None:
    state.load = clamp(state.load + load_delta, 0.0, 100.0)

    cooling_effect = COOLING_EFFECT if state.cooling else 0.0
    state.temp += TEMP_LOAD_FACTOR * state.load - cooling_effect - NATURAL_COOLING
    state.temp += temp_delta

    if state.temp > ERROR_TEMP_THRESHOLD:
        state.error_rate += (state.temp - ERROR_TEMP_THRESHOLD) * ERROR_RATE_TEMP_FACTOR
    else:
        state.error_rate *= ERROR_RATE_DECAY
    state.error_rate += error_rate_delta

    state.health -= (
        max(0.0, state.temp - ERROR_TEMP_THRESHOLD) * HEALTH_TEMP_FACTOR
        + state.error_rate * HEALTH_ERROR_RATE_FACTOR
    )
    state.health += HEALTH_RECOVERY

    state.power = compute_power(state.load, state.cooling)

    state.load = clamp(state.load, 0.0, 100.0)
    state.temp = max(0.0, state.temp)
    state.error_rate = clamp(state.error_rate, 0.0, 100.0)
    state.health = clamp(state.health, 0.0, 100.0)
    state.power = max(0.0, state.power)


def _self_test() -> None:
    base = ServerState(load=50.0, temp=40.0, error_rate=0.0, health=100.0, cooling=False)
    apply_physics(base)
    temp_no_cooling = base.temp
    power_no_cooling = base.power

    cool = ServerState(load=50.0, temp=40.0, error_rate=0.0, health=100.0, cooling=True)
    apply_physics(cool)
    temp_with_cooling = cool.temp
    power_with_cooling = cool.power

    assert temp_with_cooling < temp_no_cooling
    assert power_with_cooling > power_no_cooling

    hot = ServerState(load=90.0, temp=75.0, error_rate=0.0, health=100.0, cooling=False)
    apply_physics(hot)
    assert hot.error_rate > 0.0

    assert 0.0 <= hot.health <= 100.0
    assert 0.0 <= hot.error_rate <= 100.0


if __name__ == "__main__":
    _self_test()
    print("rules.py self-test OK")
