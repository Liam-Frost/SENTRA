# Data Model

Source of truth: `docs/00_PROJECT_CONTEXT.md`

## Fleet domain

### Nodes

Represents a managed server.

Important fields:

- `id`
- `hostname`
- `ip`
- `os`
- `arch`
- `status`
- `created_at`
- `updated_at`

### Agents

Represents the installed probe identity associated with a node.

Important fields:

- `id`
- `node_id`
- `hostname`
- `version`
- `capabilities`
- `last_seen_at`

### Metrics

Two layers are used:

- `node_metrics_latest`
- `node_metric_samples`

Stored metrics include:

- CPU
- memory
- disk
- network in/out
- temperature
- error rate
- health
- power

## Projects and load balancers

### Projects

- `id`
- `name`
- `description`
- `created_at`
- `updated_at`

### Load balancers

- `id`
- `project_id`
- `node_id`
- `type`
- `status`
- `listen_port`
- `config`
- `created_at`
- `updated_at`

One project can own multiple load balancer nodes.

## Operation templates

### Operation templates

- `id`
- `name`
- `description`
- `created_at`
- `updated_at`

### Operation template steps

- `id`
- `template_id`
- `position`
- `name`
- `command`
- `timeout_sec`
- `continue_on_error`

## Execution runtime

Template executions currently reuse the existing operations runtime.

### Operations

Used to persist execution jobs.

For template-driven executions:

- `action_type = template_execution`
- `parameters.template_id`
- `parameters.template_name`
- `parameters.steps[]`

### Operation runs

One record per node target.

### Operation run logs

Stores streamed or uploaded run logs.

## Load balancer policy domain

### LB policies

- `id`
- `project_id`
- `name`
- `description`
- `status`
- `dr_mode`
- `health_check_path`
- `health_check_interval_sec`
- `failure_threshold`
- `recovery_threshold`
- `auto_failback`
- `created_at`
- `updated_at`

### LB policy allocations

- `id`
- `policy_id`
- `node_id`
- `weight`
- `enabled`
- `priority`

## Events

Events remain the shared audit timeline.

Current common event areas:

- node lifecycle
- agent lifecycle
- operation template activity
- execution activity
- project changes
- load balancer changes
- policy changes
- incident signals from metrics thresholds
