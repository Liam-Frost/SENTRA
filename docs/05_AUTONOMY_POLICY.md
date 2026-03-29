# Autonomy And Safety Notes

Source of truth: `docs/00_PROJECT_CONTEXT.md`

SENTRA no longer presents generic autonomy as the primary product workflow.

## Current position

- the main product is operator-driven
- automation is explicit through operation templates and policy apply flows
- AI remains advisory only
- simulator autonomy is now debug/demo-only

## Safety principles that still matter

- agents execute only server-provided work items
- all executions must be logged through operations and event records
- high-risk actions should remain visible and auditable
- simulator mode must stay hidden unless explicitly enabled

## Simulation note

If simulation mode is enabled, legacy autonomy behavior may still be exposed for
debugging and demo purposes. That behavior is not the canonical product path and
must not be used as the main reference for feature design.
