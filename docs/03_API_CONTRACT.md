# API Contract

Source of truth: `docs/00_PROJECT_CONTEXT.md`

Base path: `/api`

## Core control-plane endpoints

### Capabilities

- `GET /api/capabilities`

Returns feature visibility such as simulation availability and current backend mode.

### Dashboard

- `GET /api/dashboard`

Returns control-plane summary metrics, node summaries, and recent operation executions.

### Nodes

- `GET /api/nodes`
- `POST /api/nodes`
- `GET /api/nodes/:id`

Used for fleet listing, manual node upsert, and per-node detail.

### Projects

- `GET /api/projects`
- `POST /api/projects`
- `PUT /api/projects/:id`
- `DELETE /api/projects/:id`

### Load balancers

- `GET /api/load-balancers?project_id=...`
- `POST /api/load-balancers`
- `PUT /api/load-balancers/:id`
- `DELETE /api/load-balancers/:id`

`POST /api/load-balancers` supports:

- single-node create with `nodeId`
- multi-node create with `nodeIds`

### Load balancer policies

- `GET /api/lb-policies`
- `POST /api/lb-policies`
- `GET /api/lb-policies/:id`
- `PUT /api/lb-policies/:id`
- `DELETE /api/lb-policies/:id`
- `POST /api/lb-policies/:id/apply`

### Operation templates

- `GET /api/operation-templates`
- `POST /api/operation-templates`
- `GET /api/operation-templates/:id`
- `PUT /api/operation-templates/:id`
- `DELETE /api/operation-templates/:id`
- `POST /api/operation-templates/:id/execute`

### Operation executions

- `GET /api/operation-executions`
- `GET /api/operation-executions/:id`

### Legacy operations endpoints still in use by runtime plumbing

- `GET /api/operations`
- `POST /api/operations`
- `GET /api/operations/:id`
- `DELETE /api/operations/:id`
- `POST /api/operations/:id/cancel`
- `POST /api/operations/:id/retry`
- `GET /api/operations/:id/logs`

These power template execution storage and agent command flow.

## Agent endpoints

- `POST /api/agents/register`
- `POST /api/agents/heartbeat`
- `POST /api/agents/metrics`
- `GET /api/agents/commands/next`
- `POST /api/agents/commands/:run_id/logs`
- `POST /api/agents/commands/:run_id/result`

## Event endpoints

- `GET /api/events`

Event types currently used include:

- `incident`
- `agent`
- `node`
- `operation`
- `project`
- `load_balancer`
- `policy`
- plus simulator/debug event types when simulation mode is enabled

## Simulation and debug endpoints

These are hidden unless `SENTRA_SIM_ENABLED=true`:

- `GET /api/state`
- `POST /api/tick`
- `POST /api/fault`
- `POST /api/autonomy`
- `POST /api/reset`
- `GET /api/realtime`
- `POST /api/realtime`

When disabled, they should not be considered part of the primary product contract.

## Error shape

Validation errors use:

```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Human readable explanation"
  }
}
```
