# SENTRA

## Server Operations Control Plane

SENTRA is a server monitoring and operations panel built around three product areas:

- fleet visibility for probe-managed nodes
- reusable shell operation templates and execution history
- project-scoped load balancer and traffic policy management

The repository still contains a simulation module for demo and debugging, but the
main product direction is now a real control plane backed by PostgreSQL, probe
agents, and project-centric operational workflows.

## What the product does

- registers real nodes through a probe/agent
- receives heartbeats and latest metrics from managed servers
- stores an auditable event timeline
- lets operators create shell-command templates with ordered steps
- runs those templates on selected nodes
- manages projects and the load balancer nodes that belong to each project
- manages project-level load balancer policies such as traffic allocation and
  disaster recovery mode

## Product structure

Frontend areas:

- `Dashboard`: control-plane overview
- `Fleet`: registered nodes and health state
- `Projects`: project library and project detail overlays
- `Policies`: load balancer policy library and detail overlays
- `Operations`: operation template library and detail overlays
- `Events`: audit timeline

Backend areas:

- Flask API for UI and probe agents
- PostgreSQL/SQLite persistence layer
- operation template execution orchestration
- load balancer policy CRUD and apply workflow
- event logging and dashboard aggregation

Agent areas:

- agent registration
- heartbeat and metrics reporting
- command polling
- ordered shell step execution for operation templates

## Runtime modes

Default mode is real operations mode.

Simulation mode still exists, but it is hidden unless explicitly enabled with:

- `SENTRA_SIM_ENABLED=true`

When simulation mode is disabled:

- simulation controls are not shown in the UI
- simulation-only endpoints return `404`

## Tech stack

Backend:

- Python
- Flask
- psycopg
- PostgreSQL or SQLite fallback
- Pytest

Frontend:

- React
- TypeScript
- Vite

Agent:

- Python
- requests
- psutil

## Local development

Start both services:

Windows:

```powershell
scripts/dev_all.ps1
```

macOS/Linux:

```bash
scripts/dev_all.sh
```

Default local URLs:

- backend: `http://localhost:5000`
- frontend: `http://localhost:5173`

## Documentation map

Core product docs live in `docs/`:

- `docs/00_PROJECT_CONTEXT.md`
- `docs/01_VISION_AND_SCOPE.md`
- `docs/02_SYSTEM_ARCHITECTURE.md`
- `docs/03_API_CONTRACT.md`
- `docs/04_DATA_MODEL.md`
- `docs/05_AUTONOMY_POLICY.md`
- `docs/09_RISK_AND_FALLBACK.md`
- `docs/10_RELEASE_PLAN.md`
- `docs/11_DEMO_PLAYBOOK.md`

## Notes

- the simulation module is now a debug/demo capability, not the primary product
- current load balancer application flow is template-driven and still uses placeholder
  shell commands for real balancer reload work
- the repository contains both current control-plane logic and some legacy simulator-era
  modules that may be retired later
