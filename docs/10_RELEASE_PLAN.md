# Release Plan

## Current phase

Control-plane foundation and product repositioning.

## Milestones

### M1 - Fleet foundation

- agent registration
- heartbeat and metrics ingestion
- node inventory and dashboard aggregation

### M2 - Operations foundation

- operation template CRUD
- ordered shell-step execution
- execution logs and status tracking

### M3 - Project and load balancer management

- project CRUD
- project-scoped load balancer node CRUD

### M4 - Policy foundation

- load balancer policy CRUD
- per-node traffic allocation
- DR configuration
- apply workflow via execution pipeline

### M5 - Production hardening follow-ups

- real load balancer adapters
- auth/RBAC
- approvals and scheduling
- deployment hardening

## Release readiness checklist

- [ ] PostgreSQL-backed deployment path documented and verified
- [ ] Agent registration and execution flow stable
- [ ] Project and load balancer management validated in UI
- [ ] Policy apply flow validated end-to-end
- [ ] Dashboard reflects current product model rather than simulator metrics
