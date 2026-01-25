# System Architecture

This document describes SENTRA's runtime architecture and data flow.

Source of truth: `docs/00_PROJECT_CONTEXT.md`.

---

## High-Level Diagram

```
React Frontend
    |
    v
Flask REST API
    |
    v
Simulation Engine
    |
    v
Autonomy Controller
    |
    v
SQLite Event Store
    |
    v
AI Explanation Layer
```

Key separation:

- Autonomy controller executes actions.
- AI layer is planner/explainer only.

---

## Responsibilities

### Frontend (React + TypeScript)

- Visualize server metrics and incident states
- Provide controls for:
  - tick advance
  - fault injection
  - autonomy toggle
- Display event timeline

### Backend API (Flask)

- Exposes core REST endpoints
- Validates inputs
- Orchestrates simulation, controller, persistence, AI calls

### Simulation Engine

- Owns world state (3 servers + `incoming_traffic`)
- Updates state once per tick using the defined physical rules
- Applies fault effects during ticks

### Autonomy Controller

- Detects incidents based on thresholds
- Chooses actions using the fixed priority order
- Enforces safety constraints (notably restart gating)
- Implements self-correction loop (wait 5 ticks, re-check)

### Event Store (SQLite)

- Persists timeline of:
  - faults
  - incidents
  - actions
  - AI outputs

### AI Layer

- Generates explanation and recommendations
- Output is strict JSON (validated)
- Output is stored to the event timeline

---

## Core Runtime Loops

### Manual (Human-Driven)

1. User calls `/api/tick`
2. Simulation advances N ticks
3. State is returned and/or refreshed via `/api/state`
4. Events are available via `/api/events`

### Autonomous (System-Driven)

Each tick (every 1 second):

1. Simulation advances 1 tick
2. Controller detects incident thresholds
3. If incident exists, controller executes safe actions (rule-based)
4. Controller waits 5 ticks before escalating (self-correction)
5. Events are written to SQLite
6. AI may be called to generate explanation (advisory only)
