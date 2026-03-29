# Project Context

This file is the authoritative product context for SENTRA.

## Identity

- Product: SENTRA
- Current form: server operations control plane
- Primary users: operators managing fleets, reusable shell automations, and
  project-scoped load balancer policies

## Current mission

Build a practical control plane that can:

- register and monitor managed servers through probe agents
- execute reusable, ordered shell operation templates on selected nodes
- manage projects and project-scoped load balancer nodes
- manage traffic allocation and disaster recovery policies per project
- keep a clear audit trail for node, policy, and execution activity

## Product domains

### Fleet

- nodes are registered dynamically by agents
- each node reports heartbeat and metrics
- node identity is no longer fixed to `S1/S2/S3`

### Operations

- users create reusable operation templates
- each template contains ordered shell steps
- users execute templates on selected nodes
- executions are auditable and return logs/output per node

### Projects

- projects are first-class ownership units
- load balancer nodes belong to projects
- load balancer management is accessed from project detail flows

### Policies

- policies are specifically for load balancer traffic and DR behavior
- policies are not a generic rule engine anymore
- policy apply creates execution work against load balancer nodes

## Runtime model

Default product mode:

- real control-plane mode

Optional debug mode:

- simulator mode behind `SENTRA_SIM_ENABLED=true`

Simulation is retained for demonstration/debugging, but it is not the main product.

## Persistence

- preferred database: PostgreSQL
- fallback database: SQLite

Core persisted areas:

- nodes, agents, heartbeats, metrics
- projects, load balancers
- operation templates, executions, logs
- load balancer policies and allocations
- events

## Current UI model

The UI uses library-first pages:

- main pages list domain objects
- detail/edit/create are opened from overlays

This is intentional and should remain the default interaction pattern.

## Constraints

- AI is optional and advisory only
- simulation features must remain hidden by default
- high-risk execution features should stay auditable
- product docs must describe the real control plane first, and simulation second
