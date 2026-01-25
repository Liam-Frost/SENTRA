# Vision And Scope

This document defines SENTRA's vision, scope, and explicit non-goals.

Source of truth: `docs/00_PROJECT_CONTEXT.md`.

---

## Vision

Build a fully autonomous, self-correcting micro data center control system that
can monitor, diagnose, decide, and act without human intervention.

This is an exploration prototype for "removing the human from the loop" in a
controlled simulated environment.

---

## Target Scenario

- Environment: simulated micro data center
- Servers: `S1`, `S2`, `S3`
- Time: discrete ticks (1 tick = 1 second)
- Inputs:
  - global `incoming_traffic` (0-300)
  - fault injection via API

---

## In Scope (Stabilization + Demo)

- Physical simulation rules and server state variables as defined
- Incident detection thresholds as defined
- Rule-based autonomy controller
- Self-correction mechanism (wait 5 ticks, re-evaluate, escalate)
- AI planner/explainer integration (strict JSON, advisory only)
- SQLite event timeline persistence
- Frontend dashboard for:
  - state visualization
  - fault injection
  - autonomy toggle
  - event timeline

---

## Out Of Scope (For This Phase)

- Production deployment and real telemetry integration
- Authentication/authorization model
- Multi-cluster federation
- RL-based control (future extension)
- Cloud hosting and distributed persistence

---

## Non-Goals / Constraints

- AI cannot execute actions directly.
- All state updates happen via tick.
- Safety constraints override autonomy.

---

## Success Criteria

Project success means:

- Autonomous loop runs >= 30 minutes without crash
- System recovers from injected faults without human intervention
- AI explanations are coherent and stored as events
- Demo is reproducible
