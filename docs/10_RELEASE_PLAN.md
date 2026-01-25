# Release Plan

Current phase:

```
Stabilization + Demo Preparation
```

This plan focuses on reliability, observability, and demo reproducibility.

---

## Milestones

### M1 - Simulation Correctness

- Implement tick-based physical rules as defined
- Maintain required server state variables for S1/S2/S3
- Apply fault effects per tick

### M2 - Autonomy Reliability

- Implement incident thresholds
- Implement action priority strategy
- Implement restart safety constraint
- Implement self-correction loop (wait 5 ticks, re-evaluate, escalate)

### M3 - Observability

- Persist events to SQLite
- Provide `/api/events` timeline endpoint
- Visualize timeline and state in frontend

### M4 - AI Explanations

- Trigger AI on incidents
- Enforce strict JSON validation
- Store AI outputs as timeline events

### M5 - Demo Readiness

- Demo run is reproducible
- Autonomy loop runs >= 30 minutes without crash
- System recovers from injected faults

---

## Demo-Ready Checklist

- [ ] Fault injection works for all supported types
- [ ] Incidents trigger reliably at thresholds
- [ ] Controller recovers using safe actions
- [ ] Restart gating is enforced and logged
- [ ] AI output is validated and visible
- [ ] Timeline persists across restarts (SQLite)
