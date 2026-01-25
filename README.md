# SENTRA

## Self-Governing Autonomous Data Center Operations System

SENTRA is a fully autonomous operations and resilience system for micro-scale data centers.
It continuously monitors infrastructure health, detects anomalies, generates corrective strategies, and executes recovery actions without human intervention.

The project addresses the challenge of building reliable, safe, and explainable AI-driven control systems in dynamic operational environments, aligned with Track 2: **AI + Automation – Fully Autonomous Solutions (“Removing the Human from the Loop”)**.

---

## 1. Motivation and Problem Statement

Modern data center operations rely heavily on manual monitoring and intervention. This model suffers from:

* Limited reaction speed under failure conditions
* High operational cost
* Human-induced errors
* Poor scalability in complex systems

As infrastructures grow in size and complexity, manual supervision becomes increasingly ineffective.

SENTRA explores an alternative paradigm: **self-governing infrastructure systems** capable of independent monitoring, decision-making, execution, and recovery.

---

## 2. Project Objectives

The project aims to design and prototype a closed-loop autonomous control system that:

1. Continuously senses system state
2. Detects abnormal operating conditions
3. Generates mitigation strategies
4. Executes recovery actions autonomously
5. Evaluates outcomes and self-corrects
6. Records all decisions for auditability

This loop operates without human approval during normal operation.

---

## 3. Target Scenario

SENTRA operates on a simulated micro data center composed of three servers (S1, S2, S3).

Each server maintains the following state variables:

* Load
* Temperature
* Error rate
* Power consumption
* Health score
* Cooling state

An external traffic generator produces dynamic workload patterns.

This environment enables controlled evaluation of autonomous behavior under realistic stress conditions.

---

## 4. System Architecture

```
React Frontend
      ↓
Flask API Gateway
      ↓
Simulation Engine
      ↓
Autonomy Controller
      ↓
Safety Validator
      ↓
SQLite Event Store
      ↓
AI Explanation Layer
```

The architecture enforces separation between perception, decision, execution, and explanation.

---

## 5. Autonomous Control Design

### 5.1 Monitoring and Detection

System state is updated at fixed intervals (tick-based simulation).
Incidents are triggered when predefined thresholds are exceeded.

### 5.2 Decision Layer

A hybrid decision mechanism is adopted:

* Rule-based controller ensures deterministic stability
* AI planner provides interpretive and strategic reasoning

This prevents uncontrolled behavior while retaining adaptability.

### 5.3 Execution Layer

Supported actions include:

* Load rerouting
* Traffic throttling
* Cooling activation
* Controlled restart

All actions are validated by safety policies before execution.

### 5.4 Self-Correction

After action execution, the system reevaluates its state.
If recovery is insufficient, escalation strategies are applied.

---

## 6. Safety, Ethics, and Governance

SENTRA incorporates explicit governance mechanisms:

* AI does not directly execute actions
* High-risk operations are constrained
* Rollback conditions are mandatory
* Full decision traceability is enforced
* Manual override remains available

These mechanisms prevent autonomy from becoming loss of control.

---

## 7. Explainable AI Integration

AI is used exclusively for:

* Root cause analysis
* Action recommendation
* Risk assessment
* Rollback planning

Outputs follow strict structured formats to ensure interpretability.

This design enables transparency in autonomous decision-making.

---

## 8. Technology Stack

### Backend

* Python 3.9+
* Flask
* SQLite
* Requests
* Pytest

### Frontend

* React
* TypeScript
* Vite
* Tailwind CSS

### AI

* OpenAI-compatible APIs
* JSON schema validation

---

## 9. Core APIs

Canonical contract: `docs/03_API_CONTRACT.md`

| Endpoint      | Method | Function               |
| ------------- | ------ | ---------------------- |
| /api/state    | GET    | Current state snapshot |
| /api/tick     | POST   | Advance simulation     |
| /api/events   | GET    | Event history          |
| /api/autonomy | POST   | Toggle autonomy        |
| /api/fault    | POST   | Inject fault           |
| /api/reset    | POST   | Reset system           |

---

## 10. Experimental Setup

The simulation supports:

* Deterministic replay via seed control
* Fault injection
* Workload variability
* Controlled escalation scenarios

This enables reproducible evaluation of autonomy performance.

---

## 11. Documentation Governance

SENTRA maintains a structured documentation system in `docs/` covering:

* System context
* Architecture
* API contracts
* Autonomy policy
* Risk management
* Decision logs

This ensures continuity across AI-assisted and human development cycles.

---

## 12. Deployment and Execution

### Prerequisites

* Python 3.9+
* Node.js 18+
* npm 9+

### Startup

Windows:

```
scripts/dev_all.ps1
```

macOS/Linux:

```
scripts/dev_all.sh
```

Services:

* Backend: [http://localhost:5000](http://localhost:5000)
* Frontend: [http://localhost:5173](http://localhost:5173)

---

## 13. Evaluation Criteria

SENTRA is evaluated based on:

* Stability under sustained load
* Recovery time after fault injection
* Decision consistency
* Safety policy compliance
* Explainability of actions
* Reproducibility

---

## 14. Future Directions

Planned extensions include:

* Reinforcement learning controllers
* Multi-node federation
* Real telemetry integration
* Policy-driven governance engines
* Cloud-native deployment

---

## 15. License

MIT License. See `LICENSE`.

---

## 16. Project Contribution Summary

SENTRA demonstrates:

* A complete autonomous control loop
* Integrated safety governance
* Explainable AI reasoning
* Reproducible experimentation environment
* Production-oriented system architecture

The project provides a reference implementation for safe and governed autonomous infrastructure systems.

