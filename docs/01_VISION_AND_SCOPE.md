# Vision And Scope

Source of truth: `docs/00_PROJECT_CONTEXT.md`

## Vision

Turn SENTRA into a usable server operations console instead of a simulator-first
autonomy demo.

The product should help operators manage real nodes, reusable operations, projects,
and project-level load balancer behavior from one control plane.

## In scope

- agent registration, heartbeat, and latest metrics ingestion
- node inventory and control-plane dashboarding
- operation template CRUD
- ordered shell-step execution on selected nodes
- project CRUD
- load balancer node CRUD under projects
- load balancer policy CRUD and apply flow
- event/audit timeline
- simulator kept as hidden debug/demo capability

## Out of scope for the current phase

- full production-grade authz/authn
- advanced scheduling and approvals for operations
- automatic load balancer reconfiguration adapters for every real implementation
- Kubernetes/cloud load balancer integrations
- autonomous self-healing as the primary product story

## Non-goals

- do not present SENTRA as a generic autonomous decision engine in primary docs
- do not treat simulation as the primary product workflow
- do not keep first-level pages overloaded with creation and edit forms

## Success criteria

- operators can register real nodes and inspect fleet state
- operators can create and run operation templates on chosen nodes
- operators can manage projects and load balancer nodes under each project
- operators can define per-project traffic and DR policies
- key actions are visible in the event timeline
