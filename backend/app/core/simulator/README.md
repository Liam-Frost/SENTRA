# Simulator Module

This module is retained for debug and demo support.

It is no longer the primary product architecture for SENTRA.

## Current status

- hidden behind `SENTRA_SIM_ENABLED=true`
- used for demo/debug scenarios only
- not the main control-plane workflow described in product docs

## What it still contains

- world model and tick loop
- 3-node simulation state
- fault injection logic
- legacy simulator actions and rules

## Documentation rule

If you update this module, keep its docs aligned with the fact that it is now a
secondary capability and not the main user-facing product path.
