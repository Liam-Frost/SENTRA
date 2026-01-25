# Autonomy Policy

This document defines SENTRA's autonomy behavior and safety constraints.

Source of truth: `docs/00_PROJECT_CONTEXT.md`.

---

## Safety Principles

- Safety rules override autonomy.
- AI is advisory only (planner/explainer), never an executor.
- All state updates happen via tick.
- Incidents and actions must be logged.

---

## Incident Detection

Incident triggered when:

```
temp > 80
OR error_rate > 5%
OR health < 60
```

---

## Control Strategy (Rule-Based)

Priority order:

1. enableCooling
2. reroute
3. throttle
4. restart (only if safe)

---

## Restart Safety Constraint

Restart allowed only if:

```
temp < 85 AND error_rate > 5
```

If restart is unsafe, the controller must not execute it and must log a
recommendation/block reason.

---

## Self-Correction

After action execution:

```
wait 5 ticks
re-evaluate state
if incident persists:
  escalate actions
```

Escalation means moving forward in the priority order.

---

## Logging Requirements

The timeline must include:

- fault injection events
- incident detection events
- controller decisions (including blocked actions)
- action execution events
- AI explanation events (strict JSON)
