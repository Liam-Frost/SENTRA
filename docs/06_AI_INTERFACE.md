# AI Interface

This document defines how SENTRA uses AI.

Source of truth: `docs/00_PROJECT_CONTEXT.md`.

---

## Role

Planner and explainer only. AI must not execute actions directly.

AI responsibilities:

- Explain incident causes
- Suggest an action sequence
- Evaluate risks
- Provide rollback conditions

---

## Output Contract (Strict JSON)

The AI must return valid JSON with the following shape:

```json
{
  "root_causes": [],
  "recommended_actions": [],
  "risks": [],
  "rollback_conditions": []
}
```

Array guidance:

- Each array contains short strings (human-readable).
- No extra top-level keys are allowed.

---

## Validation Schema

```json
{
  "type": "object",
  "required": [
    "root_causes",
    "recommended_actions",
    "risks",
    "rollback_conditions"
  ],
  "properties": {
    "root_causes": {"type": "array", "items": {"type": "string"}},
    "recommended_actions": {"type": "array", "items": {"type": "string"}},
    "risks": {"type": "array", "items": {"type": "string"}},
    "rollback_conditions": {"type": "array", "items": {"type": "string"}}
  },
  "additionalProperties": false
}
```

---

## Example Output

```json
{
  "root_causes": [
    "Network spike increased load, causing temperature to rise above threshold"
  ],
  "recommended_actions": [
    "enableCooling on the affected server",
    "reroute load away from the affected server",
    "throttle incoming_traffic if incident persists"
  ],
  "risks": [
    "Cooling increases power consumption",
    "Rerouting may increase load on other servers"
  ],
  "rollback_conditions": [
    "If temp stays > 85 for 5 ticks, block restart and continue throttling",
    "If health continues to drop below 60 after 2 escalation steps, disable autonomy"
  ]
}
```
