# SENTRA Knowledge Package (Authoritative)

This file contains the authoritative project context for SENTRA.

All documentation generation and code changes must be consistent with the
information in this file.

---

## 1. Project Identity

- Project Name: SENTRA
- Full Name: Self-Governing Autonomous Data Center System
- Track: AI + Automation - Fully Autonomous Solutions
- Goal: Removing Human from the Loop

Mission statement:

Build a fully autonomous, self-correcting micro data center control system that
can monitor, diagnose, decide, and act without human intervention.

---

## 2. Problem Domain

Domain: Micro Data Center Operations & Optimization

Problem: Traditional data center operations rely on manual monitoring and
intervention, causing:

- Slow reaction time
- High operational cost
- Scalability limits
- Human error risks

Objective:

Automate anomaly detection, diagnosis, response, and recovery in a simulated
environment.

---

## 3. Target Scenario

Environment: Simulated micro data center with 3 servers:

```
S1, S2, S3
```

Server state variables:

| Variable   | Type  | Range      | Meaning           |
| ---------- | ----- | ---------- | ----------------- |
| load       | float | 0-100      | CPU/traffic load  |
| temp       | float | C          | Temperature       |
| error_rate | float | %          | Failure rate      |
| power      | float | Watts      | Power consumption |
| health     | int   | 0-100      | Health score      |
| cooling    | bool  | true/false | Cooling enabled   |

Global input:

```
incoming_traffic: 0-300
```

---

## 4. Physical Simulation Rules

Each tick (1 second):

Load -> Temperature

```
temp += 0.02 * load - cooling_effect - natural_cooling
```

Temperature -> Error

```
if temp > 70:
  error_rate += (temp - 70) * 0.02
else:
  error_rate *= 0.95
```

Error & Temp -> Health

```
health -= (max(0,temp-70)*0.2 + error_rate*0.5)
health += 0.2
```

Power

```
power = 80 + load*2 + (cooling ? 40 : 0)
```

---

## 5. Fault Injection Types

Faults are injected via API.

| Type          | Effect                     |
| ------------- | -------------------------- |
| overheat      | +3 C per tick              |
| hardware_fail | +2% error per tick         |
| network_spike | +30 load for target server |

---

## 6. Autonomous Control Logic

Detection thresholds: incident triggered when:

```
temp > 80
OR error_rate > 5%
OR health < 60
```

Control strategy (rule-based), priority order:

1. Enable cooling
2. Reroute load
3. Throttle
4. Restart (only if safe)

Restart safety constraint:

Restart allowed only if:

```
temp < 85 AND error_rate > 5
```

Otherwise: log recommendation only.

---

## 7. Actions Supported

| Action         | Effect                    |
| -------------- | ------------------------- |
| reroute        | Move load between servers |
| throttle       | Reduce incoming load      |
| enableCooling  | Activate cooling          |
| disableCooling | Deactivate cooling        |
| restart        | Reset error & temp        |

---

## 8. AI Role (Planner & Explainer Only)

AI is NOT allowed to execute actions directly.

AI responsibilities:

- Explain incident causes
- Suggest action sequence
- Evaluate risks
- Provide rollback conditions

Output format (strict JSON):

```json
{
  "root_causes": [],
  "recommended_actions": [],
  "risks": [],
  "rollback_conditions": []
}
```

---

## 9. Self-Correction Mechanism

After action execution:

```
wait 5 ticks
re-evaluate state
if incident persists:
  escalate actions
```

---

## 10. System Architecture

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

---

## 11. Tech Stack

Frontend:

- React
- TypeScript
- Vite
- Tailwind

Backend:

- Python
- Flask
- Requests
- dotenv

Database:

- SQLite

AI:

- OpenAI-compatible API

---

## 12. Core APIs

| Endpoint      | Method | Purpose             |
| ------------- | ------ | ------------------- |
| /api/state    | GET    | Current world state |
| /api/tick     | POST   | Advance simulation  |
| /api/fault    | POST   | Inject fault        |
| /api/events   | GET    | Event timeline      |
| /api/autonomy | POST   | Toggle autonomy     |

---

## 13. Repository Governance

Docs system: `docs/` contains:

| File                      | Purpose        |
| ------------------------- | -------------- |
| 00_PROJECT_CONTEXT.md     | Global context |
| 01_VISION_AND_SCOPE.md    | Scope control  |
| 02_SYSTEM_ARCHITECTURE.md | Architecture   |
| 03_API_CONTRACT.md        | API spec       |
| 04_DATA_MODEL.md          | Data schema    |
| 05_AUTONOMY_POLICY.md     | Safety rules   |
| 06_AI_INTERFACE.md        | AI contract    |
| 07_TASK_REGISTRY.md       | Tasks          |
| 08_DECISION_LOG.md        | Decisions      |
| 09_RISK_AND_FALLBACK.md   | Risks          |
| 10_RELEASE_PLAN.md        | Timeline       |
| 11_DEMO_PLAYBOOK.md       | Demo script    |

---

## 14. Team Structure

- Member A (System Integrator)
  - Frontend
  - API contract
  - Tick system
  - Integration
- Member B (Simulation Engineer)
  - World model
  - Rules
  - Fault system
- Member C (Autonomy & AI Engineer)
  - Controller
  - AI layer
  - Database
  - Events

---

## 15. Project Phase

Current phase:

```
Stabilization + Demo Preparation
```

Primary focus:

- Stability
- Visualization
- Autonomous loop reliability
- Demo reproducibility

---

## 16. Key Constraints

- AI cannot execute actions
- All state updates via tick
- All major changes logged
- Safety rules override autonomy
- Docs are authoritative

---

## 17. Success Criteria

- Autonomous loop runs >= 30 minutes without crash
- System recovers from injected faults
- AI explanations are coherent
- Demo is reproducible
- No human intervention required

---

## 18. Long-Term Vision

Future extensions:

- RL-based controller
- Multi-cluster federation
- Real telemetry integration
- Federated learning
- Cloud deployment
