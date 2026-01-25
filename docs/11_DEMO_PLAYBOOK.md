# Demo Playbook

This file provides a reproducible demo script for SENTRA.

Goal: demonstrate the full autonomous loop (detect -> decide -> act -> recover)
with AI explanations (planner only).

Source of truth: `docs/00_PROJECT_CONTEXT.md`.

---

## Demo Setup

- Start backend (Flask)
- Start frontend (React)
- Confirm `/api/state` responds
- Confirm event store is writable (`/api/events` returns)

---

## Script

### Step 1 - Show Baseline State

- Open the dashboard
- Point out each server's variables: load, temp, error_rate, power, health, cooling

### Step 2 - Enable Autonomy

- POST `/api/autonomy` with `{ "enabled": true }`
- Explain safety model:
  - rule-based control
  - restart gated by safety constraint
  - AI is advisory only

### Step 3 - Inject network_spike

- POST `/api/fault` with `{ "type": "network_spike", "target": "S2" }`
- Observe response:
  - enableCooling
  - reroute/throttle if needed
- Show corresponding timeline entries

### Step 4 - Inject overheat

- POST `/api/fault` with `{ "type": "overheat", "target": "S1" }`
- Observe temperature threshold breach (temp > 80)
- Show AI explanation event (strict JSON) and rollback conditions

### Step 5 - Inject hardware_fail

- POST `/api/fault` with `{ "type": "hardware_fail", "target": "S3" }`
- Observe error_rate threshold breach (error_rate > 5%)
- If restart is considered, highlight restart safety gate:
  - restart only if temp < 85 AND error_rate > 5

### Step 6 - Stability Window

- Let autonomy run
- Confirm incidents clear and health recovers
- Keep running to demonstrate stability (>= 30 minutes target)

---

## Talking Points

- All state updates happen via tick (1 tick = 1 second).
- Autonomy strategy is deterministic and safety constrained.
- AI does not execute actions; it only explains and recommends.
- Events provide a complete audit timeline (faults, incidents, actions, AI).
