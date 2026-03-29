# AI Interface

Source of truth: `docs/00_PROJECT_CONTEXT.md`

## Current role

AI is optional and advisory.

It may be used for:

- summarizing incidents
- explaining likely causes
- suggesting operator follow-up actions
- helping future operational analysis

It must not be treated as the authoritative executor of node changes.

## Execution boundary

- shell execution happens through operation templates and agents
- policy application happens through explicit apply flows
- AI recommendations must not bypass those execution paths

## Documentation rule

Any AI-related documentation or UI copy should describe AI as support for human
operators, not as the core product identity.
