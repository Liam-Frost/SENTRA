# Simulator Module (World + Rules + Faults)

This folder implements SENTRA's simulation engine for the 3-server micro data center.
It owns world state, tick-based physics rules, and fault injection.

---

## Overview

- World model and tick loop
- Physical rules (temp/error/health/power)
- Fault system with durations
- Action effects (reroute/throttle/cooling/restart)

---

## Files

### `world.py`

- Owns `World` state: `tick`, `incoming_traffic`, `servers`, `traffic_split`
- Advances simulation via `World.tick(steps=1)`
- Applies actions via `World.apply_action(action, target)`
- Integrates fault effects every tick
- Supports direct execution for self-test (`python world.py`)

### `rules.py`

- Defines physics constants and formulas
- `ServerState` dataclass and JSON export via `to_dict()`
- `apply_physics()` updates temp/error/health/power per tick
- Self-test included (`python rules.py`)

### `faults.py`

- Defines supported fault types and durations
- `FaultManager` manages active faults
- `apply_tick_effects()` returns per-server deltas each tick
- Self-test included (`python faults.py`)

---

## Key data shapes

- ServerState
  - load, temp, error_rate, power, health, cooling
- WorldState
  - tick, incoming_traffic, servers{S1,S2,S3}, autonomy_enabled

See `docs/04_DATA_MODEL.md` for authoritative schema.

---

## Supported faults

- `overheat`: temp +3 per tick (duration 10)
- `hardware_fail`: error_rate +2 per tick (duration 15)
- `network_spike`: load +30 per tick (duration 5)

All values must stay aligned with `docs/03_API_CONTRACT.md`.

---

## Supported actions

- `enableCooling` / `disableCooling`
- `reroute`
- `throttle` (temperature-based ratio)
- `restart` (resets temp/error_rate and clears `hardware_fail`)

Action names follow `docs/03_API_CONTRACT.md`.

---

## Quick self-tests

Run from repo root:

```bash
python -B backend/app/core/simulator/rules.py
python -B backend/app/core/simulator/faults.py
python -B backend/app/core/simulator/world.py
```

Each prints `... self-test OK` on success.

---

## Notes

- AI is advisory only; autonomy is rule-based in the controller.
- All state updates happen via tick.
- This module is deterministic for demo reproducibility.
