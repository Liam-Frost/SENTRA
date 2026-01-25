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

Response (200):

```json
{
  "events": []
}
```

Event record shape is defined in `docs/04_DATA_MODEL.md`.

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
