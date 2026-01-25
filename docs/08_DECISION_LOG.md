# Decision Log

This file records architectural and policy decisions.

Baseline decisions are derived from `docs/00_PROJECT_CONTEXT.md`.

---

## Decisions

| ID | Date | Decision | Rationale |
| -- | ---- | -------- | --------- |
| D001 | 2026-01-24 | AI is planner/explainer only; AI never executes actions | Prevent unsafe autonomy and preserve control |
| D002 | 2026-01-24 | Simulation advances in discrete ticks (1 tick = 1 second) | Deterministic state evolution and clean audit trail |
| D003 | 2026-01-24 | Incident thresholds: temp > 80 OR error_rate > 5% OR health < 60 | Simple, consistent incident trigger |
| D004 | 2026-01-24 | Control priority: enableCooling -> reroute -> throttle -> restart | Prefer low-risk mitigation before disruptive actions |
| D005 | 2026-01-24 | Restart allowed only if temp < 85 AND error_rate > 5 | Avoid restart during overheating; safety gate |
| D006 | 2026-01-24 | Store timeline events in SQLite | Enables replay/audit and local demo persistence |
