# Decision Log

| ID | Date | Decision | Rationale |
| -- | ---- | -------- | --------- |
| D001 | 2026-03-29 | SENTRA is documented as a server operations control plane first | Product direction moved away from simulator-first positioning |
| D002 | 2026-03-29 | Simulation remains available only as a hidden debug/demo capability | Keep demo support without polluting the primary UX |
| D003 | 2026-03-29 | Operations use reusable shell-step templates | Users need repeatable multi-step operational workflows |
| D004 | 2026-03-29 | Policies are limited to load balancer traffic and DR management | Generic policy-engine UX did not match the product need |
| D005 | 2026-03-29 | Main pages follow library-first layout with detail overlays | Prevent first-level pages from becoming overloaded |
| D006 | 2026-03-29 | Load balancer node management belongs under projects | LB nodes are project-scoped operational assets |
