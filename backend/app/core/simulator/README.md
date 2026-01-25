# Simulator Module (World + Rules + Faults)

This folder implements SENTRA's simulation engine for the 3-server micro data center.
It owns world state, tick-based physics rules, and fault injection.

---

## Overview / 模块概览

- World model and tick loop / 世界模型与 tick 推进
- Physical rules (temp/error/health/power) / 物理规则（温度/错误率/健康/功耗）
- Fault system with durations / 故障系统与持续时间
- Action effects (reroute/throttle/cooling/restart) / 动作效果（转移/限流/制冷/重启）

---

## Files / 文件说明

### `world.py`

- Owns `World` state: `tick`, `incoming_traffic`, `servers`, `traffic_split`
- Advances simulation via `World.tick(steps=1)`
- Applies actions via `World.apply_action(action, target)`
- Integrates fault effects every tick
- Supports direct execution for self-test (`python world.py`)

中文说明：
- 维护世界状态与三台服务器状态
- `tick()` 驱动物理演化
- `apply_action()` 执行动作（cooling/reroute/throttle/restart）
- 每 tick 融合故障影响

### `rules.py`

- Defines physics constants and formulas
- `ServerState` dataclass and JSON export via `to_dict()`
- `apply_physics()` updates temp/error/health/power per tick
- Self-test included (`python rules.py`)

中文说明：
- 定义物理规则常量与公式
- `apply_physics()` 完成单步更新和 clamp

### `faults.py`

- Defines supported fault types and durations
- `FaultManager` manages active faults
- `apply_tick_effects()` returns per-server deltas each tick
- Self-test included (`python faults.py`)

中文说明：
- 故障注入与持续时间管理
- 每 tick 产生 load/temp/error_rate 的增量

---

## Key Data Shapes / 关键数据结构

- ServerState
  - load, temp, error_rate, power, health, cooling
- WorldState
  - tick, incoming_traffic, servers{S1,S2,S3}, autonomy_enabled

See `docs/04_DATA_MODEL.md` for authoritative schema.

---

## Supported Faults / 支持故障类型

- `overheat`: temp +3 per tick (duration 10)
- `hardware_fail`: error_rate +2 per tick (duration 15)
- `network_spike`: load +30 per tick (duration 5)

All values match `docs/00_PROJECT_CONTEXT.md`.

---

## Supported Actions / 支持动作

- `enableCooling` / `disableCooling`
- `reroute`
- `throttle` (temperature-based ratio)
- `restart` (resets temp/error_rate and clears `hardware_fail`)

Action names follow `docs/00_PROJECT_CONTEXT.md` and `docs/03_API_CONTRACT.md`.

---

## Quick Self-Tests / 快速自测

Run from repo root:

```bash
python -B backend/app/core/simulator/rules.py
python -B backend/app/core/simulator/faults.py
python -B backend/app/core/simulator/world.py
```

Each prints `... self-test OK` on success.

---

## Notes / 说明

- AI is advisory only; autonomy is rule-based in the controller.
- All state updates happen via tick.
- This module is deterministic for demo reproducibility.
