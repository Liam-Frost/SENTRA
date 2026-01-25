# SENTRA

### Self-Governing Autonomous Data Center Operations Platform

SENTRA is a modular, policy-driven autonomous operations platform designed for managing and optimizing micro data center environments. It provides a full closed-loop control system that continuously monitors infrastructure conditions, detects anomalies, plans corrective actions, and executes recovery workflows without human intervention.

The system integrates a high-fidelity tick-based simulator, a rule-governed autonomy engine, a persistent audit/event ledger, and an optional AI-based reasoning layer to enable explainable, safe, and self-correcting operations.

SENTRA is designed as a reference architecture for next-generation autonomous infrastructure management systems.

---

## Key Capabilities

* **Autonomous Control Loop**
  End-to-end closed-loop automation: monitoring → diagnosis → planning → execution → validation → correction.

* **Policy-Governed Safety Layer**
  Explicit autonomy policies and risk constraints prevent unsafe operations.

* **Explainable AI Integration**
  Optional AI layer provides structured incident analysis and remediation recommendations.

* **Persistent Audit Trail**
  All incidents, actions, and decisions are recorded in an immutable SQLite event ledger.

* **Modular Architecture**
  Clear separation between simulation, control logic, API layer, and UI enables future extensibility.

* **Reproducible Demonstration Environment**
  Deterministic simulation and scripted scenarios ensure consistent evaluation and benchmarking.

---

## System Architecture

```
+------------------+
|  React Console   |
+------------------+
         |
         v
+------------------+
|   Flask API      |
+------------------+
         |
         v
+------------------+
| Autonomy Engine  |
|  - Simulator     |
|  - Controller    |
|  - Policies      |
+------------------+
         |
         v
+------------------+
| Event Ledger     |
|  (SQLite)        |
+------------------+
         |
         v
+------------------+
| AI Reasoning     |
+------------------+
```

---

## Repository Structure

```
SENTRA/
├── backend/    # Core services: simulator, autonomy engine, API, persistence
├── frontend/   # React-based operations console
├── docs/       # Architecture, governance, API contracts, decisions
├── scripts/    # Development and orchestration utilities
└── data/        # Local runtime artifacts (SQLite, caches)
```

### Component Overview

| Directory | Responsibility                                                   |
| --------- | ---------------------------------------------------------------- |
| backend/  | Simulation engine, control logic, API services, data persistence |
| frontend/ | Operator console and visualization layer                         |
| docs/     | Governance framework and system documentation                    |
| scripts/  | Environment orchestration and automation                         |
| data/     | Local development state                                          |

---

## Quick Start (Local Development)

### Prerequisites

* Python ≥ 3.9
* Node.js ≥ 18
* npm ≥ 9

---

### Backend Services (Port 5000)

From `backend/`:

```bash
python -m venv .venv

# Windows
".venv/Scripts/python.exe" -m pip install -r requirements.txt
".venv/Scripts/python.exe" -m flask --app app.main run --port 5000

# macOS/Linux
".venv/bin/python" -m pip install -r requirements.txt
".venv/bin/python" -m flask --app app.main run --port 5000
```

---

### Frontend Console (Port 5173)

From `frontend/`:

```bash
npm install
npm run dev
```

Access the console at:

```
http://localhost:5173
```

---

### One-Command Development Environment

For integrated startup:

* Bash: `scripts/dev_all.sh`
* PowerShell: `scripts/dev_all.ps1`

This launches backend services, initializes the database, and starts the frontend console.

---

## Configuration and Environment Variables

### Backend Configuration

| Variable          | Description                                          |
| ----------------- | ---------------------------------------------------- |
| SENTRA_DB_PATH    | SQLite database location (default: data/dev.sqlite3) |
| SENTRA_AI_API_URL | AI endpoint (optional)                               |
| SENTRA_AI_API_KEY | AI authentication key (optional)                     |
| SENTRA_AI_MODEL   | AI model identifier (optional)                       |

### Frontend Configuration

| Variable          | Description                   |
| ----------------- | ----------------------------- |
| VITE_API_BASE_URL | Backend API base URL override |

All sensitive credentials must be provided via environment variables and are never committed to source control.

---

## API Documentation

Formal API specifications and usage examples are maintained in:

```
docs/03_API_CONTRACT.md
```

The contract is treated as a source of truth for frontend-backend integration.

---

## Testing and Build

### Backend Validation

```bash
cd backend

# Windows
".venv/Scripts/python.exe" -m pytest

# macOS/Linux
".venv/bin/python" -m pytest
```

### Frontend Build

```bash
cd frontend
npm run build
```

The production build outputs to `frontend/dist/`.

---

## Governance and Operational Discipline

SENTRA follows a documentation-driven governance model.

All contributors and AI agents must adhere to the following workflow:

1. Review `docs/00_PROJECT_CONTEXT.md`
2. Follow `docs/05_AUTONOMY_POLICY.md`
3. Register tasks in `docs/07_TASK_REGISTRY.md`
4. Log architectural decisions in `docs/08_DECISION_LOG.md`

This ensures long-term maintainability and prevents uncontrolled system evolution.

---

## Security and Safety Model

* AI components are advisory-only and cannot execute control actions.
* All high-impact operations are governed by explicit policy rules.
* Persistent logging enables post-incident auditing.
* Configuration isolation prevents credential leakage.

---

## Limitations and Known Constraints

* The simulation engine operates in-memory; multi-process deployments instantiate independent worlds.
* SQLite is intended for development and demonstration; production deployments should migrate to distributed storage.
* The AI layer depends on third-party service availability and latency.

---

## Roadmap

Planned enhancements include:

* Reinforcement learning-based controllers
* Multi-cluster federation
* Cloud-native deployment model
* Distributed event ledger
* Adaptive policy optimization

---

## License

This project is released under the MIT License.

---

## Contact and Contributions

For collaboration, research partnerships, or enterprise deployment inquiries, please contact the SENTRA development team.

---
