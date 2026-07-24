# PFMT Web

Vue 3 + TypeScript + Vite + Pinia + Element Plus frontend for the first PFMT phase.

## Scripts

```bash
pnpm install
pnpm dev
pnpm test
pnpm build
```

## API Base

The default API base path is `/api`. The backend also keeps `/api/v1` compatibility for earlier contracts. Override it with `VITE_API_BASE_URL` when the backend is not proxied by Vite.
