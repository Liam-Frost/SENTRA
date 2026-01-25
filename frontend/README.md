# SENTRA Frontend

The SENTRA frontend is a React console for the 3-server simulation (S1/S2/S3).
It displays live telemetry and the event timeline, and provides controls to:

- advance ticks
- inject faults
- reset the world
- toggle autonomy

## Tech stack

- React 18 + TypeScript
- Vite 5
- Tailwind CSS

## Local development

From `frontend/`:

```bash
npm install
npm run dev
```

Default URL: `http://localhost:5173`

### API proxy

In development, `frontend/vite.config.ts` proxies `/api/*` to `http://localhost:5000`.

## Routes

Hash routes:

- `#/dashboard`
- `#/fleet`
- `#/control`
- `#/events`

## API usage

API calls live in `frontend/src/api/sentra.ts` and are polled by `frontend/src/state/useSentra.ts`.
The canonical contract is `docs/03_API_CONTRACT.md`.

## Environment variables

- `VITE_API_BASE_URL` (optional): overrides the base URL used by `fetch`.
