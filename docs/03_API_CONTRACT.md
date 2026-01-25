# API Contract

This document specifies SENTRA's core HTTP APIs.

Source of truth: `docs/00_PROJECT_CONTEXT.md`.

Base path: `/api`

---

## Shared Types

### ServerState

```json
{
  "load": 0.0,
  "temp": 0.0,
  "error_rate": 0.0,
  "power": 0.0,
  "health": 100,
  "cooling": false
}
```

### WorldState

```json
{
  "tick": 0,
  "incoming_traffic": 0,
  "servers": {
    "S1": {"load": 0.0, "temp": 0.0, "error_rate": 0.0, "power": 0.0, "health": 100, "cooling": false},
    "S2": {"load": 0.0, "temp": 0.0, "error_rate": 0.0, "power": 0.0, "health": 100, "cooling": false},
    "S3": {"load": 0.0, "temp": 0.0, "error_rate": 0.0, "power": 0.0, "health": 100, "cooling": false}
  },
  "autonomy_enabled": false
}
```

Note: Implementations may include additional fields; clients should ignore
unknown fields.

### EventRecord

All fields are required. Server must emit fields as defined. Clients should
ignore unknown fields but rely on the required fields and payload shapes below.

```json
{
  "id": 1,
  "tick": 42,
  "ts": "2026-01-24T12:34:56Z",
  "type": "incident",
  "message": "temp > 80 on S2",
  "payload": {}
}
```

Allowed `type` values (strict):

- `fault`
- `incident`
- `action`
- `ai`
- `autonomy`
- `reset`

Payload shapes (required per type):

```json
// fault
{
  "type": "overheat",
  "target": "S2"
}

// incident
{
  "target": "S2",
  "metric": "temp",
  "value": 83.4,
  "threshold": 80
}

// action
{
  "action": "enableCooling",
  "target": "S2"
}

// ai
{
  "root_causes": [],
  "recommended_actions": [],
  "risks": [],
  "rollback_conditions": []
}

// autonomy
{
  "enabled": true
}

// reset
{
  "reset_events": true
}
```

Notes:

- `target` is required for `fault` and `incident` events.
- `target` is optional for `action` events (some actions may be global).
- `metric` must be one of: `temp`, `error_rate`, `health`.
- `action` must be one of: `reroute`, `throttle`, `enableCooling`, `disableCooling`, `restart`.
- If the service needs a new event type, this document must be updated first.

---

## GET /api/state

Purpose: return current world state.

Response (200): `WorldState`

---

## POST /api/tick

Purpose: advance the simulation by N ticks.

Request body:

```json
{
  "steps": 1
}
```

- `steps` is optional; default `1`
- Each step is 1 second of simulated time

Response (200): `WorldState`

---

## POST /api/fault

Purpose: inject a fault into the simulation.

Request body:

```json
{
  "type": "overheat",
  "target": "S2"
}
```

Allowed values:

- `type`: `overheat` | `hardware_fail` | `network_spike`
- `target`: `S1` | `S2` | `S3`

Response (200):

```json
{
  "ok": true
}
```

---

## GET /api/events

Purpose: return the event timeline.

Optional query parameters (recommended):

- `limit` (int)
- `since_tick` (int)
- `type` (comma-separated list of event types)
- `target` (comma-separated list of server ids)

Multi-value parameters can be provided as comma-separated values or repeated
query keys. Example:

```
/api/events?type=incident,ai&target=S1,S3&since_tick=42&limit=200
```

Filtering rules:

- `type` filters by EventRecord `type`.
- `target` filters by EventRecord `payload.target`.
- `since_tick` is inclusive.
- If multiple filters are provided, they are combined with AND.

Response (200):

```json
{
  "events": []
}
```

Event record shape is defined above and aligned with `docs/04_DATA_MODEL.md`.

---

## POST /api/autonomy

Purpose: enable/disable the autonomous loop.

Request body:

```json
{
  "enabled": true
}
```

Response (200):

```json
{
  "enabled": true
}
```

---

## POST /api/reset

Purpose: reset world state to baseline values. Optionally reset the event store.

Request body:

```json
{
  "reset_events": true
}
```

- `reset_events` is optional; default `true`
- When `reset_events` is `true`, the event store is cleared
- When `reset_events` is `false`, the event store is preserved and a `reset`
  event is appended

Response (200): `WorldState`

---

## Error Response Shape

On validation errors, return 400:

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Human readable explanation"
  }
}
```
