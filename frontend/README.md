# SENTRA Frontend

The frontend is a React control console for the SENTRA operations product.

Primary UI areas:

- `Dashboard`
- `Fleet`
- `Projects`
- `Policies`
- `Operations`
- `Events`

The UI is now organized around library-first pages:

- main pages focus on listing domain objects
- create/edit/details open in second-level overlays
- simulation controls remain hidden unless simulation mode is enabled

## Local development

From `frontend/`:

```bash
npm install
npm run dev
```

Default URL:

- `http://localhost:5173`

## API proxy

During development, `vite.config.ts` proxies `/api/*` to `http://localhost:5000`.

## Current route set

- `#/dashboard`
- `#/fleet`
- `#/projects`
- `#/policies`
- `#/operations`
- `#/events`

Simulation-enabled builds may also expose simulator-specific controls.

## Frontend API modules

- `src/api/infrastructure.ts`
- `src/api/operationTemplates.ts`
- `src/api/lbPolicies.ts`
- `src/api/operations.ts`
- `src/api/sentra.ts`

## Environment variables

- `VITE_API_BASE_URL`: optional API base override
