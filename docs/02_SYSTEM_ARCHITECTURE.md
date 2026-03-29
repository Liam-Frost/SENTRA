# System Architecture

Source of truth: `docs/00_PROJECT_CONTEXT.md`

## High-level architecture

```text
React Frontend
    |
    v
Flask REST API
    |
    +--> Fleet / Projects / Policies / Operations services
    |
    +--> PostgreSQL / SQLite
    |
    +--> Event timeline
    |
    +--> Agent command queue via operations pipeline

Probe Agent
    |
    +--> register / heartbeat / metrics
    +--> poll commands
    +--> execute ordered shell steps
    +--> upload logs and results
```

## Major backend domains

### Infrastructure service

- nodes
- agents
- heartbeats
- latest metrics
- projects
- load balancers
- dashboard summary

### Operation template service

- template CRUD
- ordered step management
- execution creation
- execution listing/detail

### Load balancer policy service

- policy CRUD
- node allocations
- DR settings
- policy apply workflow

### Operation runtime service

- persists execution records in `operations` and `operation_runs`
- exposes command polling to agents
- stores run logs and results

## Frontend structure

Primary pages:

- `Dashboard`
- `Fleet`
- `Projects`
- `Policies`
- `Operations`
- `Events`

Interaction rule:

- main page = library/listing
- overlay = create/edit/detail

## Simulation support

The simulator still exists in the codebase.

Current role:

- hidden debug or demo support
- fallback world-state provider when `SENTRA_SIM_ENABLED=true`

It is not the primary architecture described to product users.
