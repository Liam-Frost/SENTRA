# Risk And Fallback

## Risk register

| ID | Risk | Impact | Mitigation |
| -- | ---- | ------ | ---------- |
| R001 | Agent executes unsafe shell content | Node disruption | Keep execution sources explicit, audit logs enabled, and templates reviewable |
| R002 | PostgreSQL unavailable | Control-plane degradation | Keep SQLite fallback for local/dev use and fail early on missing DB config in production |
| R003 | Load balancer apply flow is still placeholder-based | Product gap between UI and real balancer runtime | Implement nginx/haproxy/traefik adapters as a follow-up milestone |
| R004 | Legacy simulator docs or flows confuse users | Product misunderstanding | Keep simulation hidden by default and clearly mark it as debug/demo-only |
| R005 | Overloaded detail overlays reduce usability | Operator friction | Continue splitting detail overlays into smaller tabs/sections as needed |

## Fallback rules

- if AI is unavailable, keep the control plane fully usable without AI
- if agent command execution fails, preserve logs and mark the execution failed rather than hiding the result
- if load balancer apply cannot complete, leave policy data intact and surface the failure through executions and events
