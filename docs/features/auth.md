# Auth

The system uses **local JWT authentication** (`STOCK_AUTH_MODE=local`). There is no OIDC integration.

## Flow

1. **Register** (`POST /api/auth/register`) or **login** (`POST /api/auth/login`) with JSON `{ "login", "password" }`.
2. Response includes `access_token` (Bearer JWT).
3. Frontend stores the token and sends `Authorization: Bearer …` on subsequent requests.
4. **First registered user** receives `is_admin=true` when `STOCK_ALLOW_SIGNUP=true`.

## Frontend

`frontend/src/contexts/AuthContext.tsx` manages token persistence and `/api/auth/me` on load. Unauthenticated users are redirected to `/login` via `ProtectedRoute`.

## Configuration

See [Configuration](configuration.md) — `STOCK_SECRET_KEY`, `STOCK_ALLOW_SIGNUP`, `STOCK_LOCAL_JWT_EXP_HOURS`, `STOCK_FRONTEND_URL`.
