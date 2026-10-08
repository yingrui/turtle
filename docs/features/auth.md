# Auth

Default mode is **`none`**: the SPA is embedded as an openKMS hosted App. openKMS authenticates the browser user and, on **every** Service-proxy request, injects identity headers. This app does **not** show a login page in that mode.

Optional **`local`** mode keeps username/password + JWT for standalone development.

## Modes

| `STOCK_AUTH_MODE` | Behavior |
|---|---|
| `none` (default) | Trust openKMS proxy headers (see below). If headers are absent (local Compose / Vite), fall back to anonymous. Login/register return 400. Frontend skips login redirect and hides logout. |
| `local` | Register / login mint HS256 JWT (`STOCK_SECRET_KEY`). Frontend stores Bearer token; unauthenticated users go to `/login`. |

## openKMS identity headers (`none` mode)

Injected by openKMS on each proxied request to the app Service:

| Header | Content |
|---|---|
| `X-Openkms-User-Id` | openKMS user id |
| `X-Openkms-Username` | login name |
| `X-Openkms-User-Name` | display name |
| `X-Openkms-User-Email` | email (omitted when empty) |
| `X-Openkms-User-Admin` | `true` / `false` |

nginx (`docker/nginx-frontend.conf`) forwards these to the backend on `/api` and `/health`. `GET /api/auth/me` returns `{ id, login, name, email, is_admin }` from the headers when present.

Do **not** expose the backend Service publicly — forged headers would be trusted.

## Local flow (only when mode is `local`)

1. **Register** (`POST /api/auth/register`) or **login** (`POST /api/auth/login`) with JSON `{ "login", "password" }`.
2. Response includes `access_token` (Bearer JWT).
3. Frontend stores the token and sends `Authorization: Bearer …` on subsequent requests.
4. **First registered user** receives `is_admin=true` when `STOCK_ALLOW_SIGNUP=true`.

## Frontend

`frontend/src/contexts/AuthContext.tsx` reads `/api/auth/mode` then `/api/auth/me`. In `none` mode the shell loads without `/login`; the header menu shows the openKMS display name when available.

## Configuration

See [Configuration](configuration.md) — `STOCK_AUTH_MODE`, `STOCK_SECRET_KEY`, `STOCK_ALLOW_SIGNUP`, `STOCK_LOCAL_JWT_EXP_HOURS`, `STOCK_FRONTEND_URL`.
