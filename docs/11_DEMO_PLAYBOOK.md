# Demo Playbook

This demo script follows the current product story, not the old simulator-first story.

## Setup

- start backend and frontend
- register at least one probe-managed node
- create at least one project

## Demo flow

### 1. Dashboard

- open `Dashboard`
- highlight fleet coverage, project count, policies, templates, and executions

### 2. Projects

- open `Projects`
- create a project from the library page
- open that project
- create one or more load balancer nodes from the project detail flow

### 3. Policies

- open `Policies`
- create a policy for the project
- set traffic allocation across two nodes
- set a DR mode
- apply the policy

### 4. Operations

- open `Operations`
- create a shell template with multiple ordered steps
- open the template detail
- run it on selected nodes
- inspect execution history and logs

### 5. Events

- open `Events`
- show that project, load balancer, policy, and execution actions are all auditable

## Optional debug/demo note

If needed, simulation mode can still be demonstrated separately by enabling
`SENTRA_SIM_ENABLED=true`, but it should be framed as a debug/demo capability.
