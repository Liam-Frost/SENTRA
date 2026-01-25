# Data Model

This document defines SENTRA's core data structures.

Source of truth: `docs/00_PROJECT_CONTEXT.md`.

---

## World State

### ServerState

| Field         | Type  | Range      | Notes |
| ------------- | ----- | ---------- | ----- |
| load          | float | 0-100      | CPU/traffic load |
| temp          | float | C          | Temperature |
| error_rate    | float | %          | Failure rate |
| power         | float | Watts      | Power consumption |
| health        | int   | 0-100      | Health score |
| cooling       | bool  | true/false | Cooling enabled |
| cooling_level | float | 0-1        | Cooling intensity (0-100%) |
| status        | str   | enum       | booting, running, restarting, thermal_shutdown, off |

### WorldState

Minimum recommended JSON shape:

```json
{
  "tick": 0,
  "incoming_traffic": 0,
  "servers": {
    "S1": {"load": 0.0, "temp": 0.0, "error_rate": 0.0, "power": 0.0, "health": 100, "cooling": true, "cooling_level": 0.0, "status": "booting"},
    "S2": {"load": 0.0, "temp": 0.0, "error_rate": 0.0, "power": 0.0, "health": 100, "cooling": true, "cooling_level": 0.0, "status": "booting"},
    "S3": {"load": 0.0, "temp": 0.0, "error_rate": 0.0, "power": 0.0, "health": 100, "cooling": true, "cooling_level": 0.0, "status": "booting"}
  },
  "autonomy_enabled": false
}
```

---

## Faults

Supported fault types:

| Type          | Effect                     |
| ------------- | -------------------------- |
| overheat      | +3 C per tick              |
| hardware_fail | +2% error per tick         |
| network_spike | +30 load for target server |

---

## Incidents

Incident trigger conditions:

```
temp > 80
OR error_rate > 5%
OR health < 60
OR load > 85
```

---

## Actions

Action identifiers (canonical):

- reroute
- throttle
- enableCooling
- disableCooling
- restart

---

## Event Timeline

The event timeline stores:

- fault injections
- incident detections
- controller decisions and executions
- AI explanation outputs

Suggested event record shape:

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

Suggested SQLite schema (implementation guidance):

```sql
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tick INTEGER NOT NULL,
  ts TEXT NOT NULL,
  type TEXT NOT NULL,
  message TEXT NOT NULL,
  payload TEXT
);
```
