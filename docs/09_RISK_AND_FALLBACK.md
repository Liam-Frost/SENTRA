# Risk And Fallback

This file tracks known risks and fallback strategies for SENTRA.

Source of truth: `docs/00_PROJECT_CONTEXT.md`.

---

## Risk Register

| ID | Risk | Impact | Mitigation |
| -- | ---- | ------ | ---------- |
| R001 | Temperature runaway | Health collapse; demo failure | Early enableCooling; reroute/throttle; block unsafe restart |
| R002 | Action thrashing/oscillation | Instability; confusing timeline | Enforce self-correction wait (5 ticks) before escalation |
| R003 | Unsafe restart during high temp | Violates safety; worsens incident | Hard gate: restart only if temp < 85 AND error_rate > 5 |
| R004 | AI invalid JSON / timeout | Breaks UI/logging | Validate schema; ignore invalid AI output; keep rule-based autonomy |
| R005 | AI hallucinated/unsafe advice | Operator confusion | Never execute AI; present as advisory; rely on safety policy |
| R006 | Event store unavailable | Lost observability | Buffer events in memory and retry; do not block simulation tick |
| R007 | Non-reproducible demo due to randomness | Unstable presentation | Prefer deterministic seeds/scenarios for demo runs |

---

## Fallback Playbook

### Disable Autonomy

- Call `/api/autonomy` with `{ "enabled": false }`.
- Continue using `/api/tick` to drive the simulation manually.

### Operate Without AI

- If AI is down or invalid, continue autonomy with rule-based controller only.
- Log AI failure as an event (type `ai_error`) if supported.

### Recover Observability

- If SQLite is locked/unavailable, buffer events in memory.
- Flush buffered events when persistence recovers.
