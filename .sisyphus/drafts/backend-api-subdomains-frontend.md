# Draft: Backend API, Subdomains, and Frontend

## Requirements (confirmed)
- run the backend API: How do I run the backend API?
- configure subdomains and the frontend: I need to configure subdomains and the frontend.

## Technical Decisions
- backend entrypoint: use `poe_trade.cli service --name api` because `README.md` documents it as the supported API startup path.
- frontend dev mode: use the existing Vite dev server and proxy because `frontend/vite.config.ts` already proxies `/api` and `/healthz` to `127.0.0.1:8080`.
- deployment target: optimize for subdomain deployment rather than local-only dev.
- auth posture: keep the operator token out of browser code because the repo marks browser-direct long-lived token storage as a non-goal.

## Research Findings
- `README.md`: local API startup requires `POE_API_OPERATOR_TOKEN` and `POE_API_CORS_ORIGINS`.
- `poe_trade/api/app.py`: protected `/api/v1/*` routes enforce bearer auth and origin allowlisting.
- `frontend/src/services/api.ts`: frontend calls relative `/api/...` paths and assumes same-origin or proxy routing.
- `frontend/src/services/api.ts`: current frontend code does not send an `Authorization` header, so direct browser calls to protected backend routes will fail unless another layer injects auth.
- `docker-compose.yml`: compose boots ClickHouse, schema migrations, and harvesters, but not the API service or frontend.
- `poe_trade/services/api.py`: the API service name is `api`; in a container deployment it should listen on `0.0.0.0:8080` for cross-container proxy reachability.
- `docker-compose.yml`: no service is attached to an external network today, so `lama-lan_backend` integration would require adding service definitions rather than just re-pointing the proxy.

## Open Questions
- Should the browser stay on same-origin `/api` routing at `app.<domain>` (matches current frontend), or should the frontend be changed to call `api.<domain>` explicitly?

## Scope Boundaries
- INCLUDE: current repo-backed startup and configuration guidance for API, CORS/origin, and frontend wiring.
- EXCLUDE: implementation changes to source code, deployment automation, or reverse-proxy config that does not yet exist in repo.
