# Kowalski frontend

A React and TypeScript client for the Flask API. The current screens are sign-in
and account details. Scan submission and history are planned.

## Local development

With Node.js 22.12+ and npm, start the [API](../README.md#run-backend-locally)
on port 5000, then run from the repository root:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open [http://127.0.0.1:3000/login](http://127.0.0.1:3000/login). Vite proxies `/api/*` to
`http://127.0.0.1:5000/*`. Set `KOWALSKI_API_URL` in `frontend/.env.local` if the
backend runs on another origin.

## Sign in

Use an existing account, or register one by sending `email`, `username`,
`first_name`, `last_name`, and `password` as JSON to `POST /auth/register` on
the Flask API. The UI currently has no registration form.

Enter the email or username and password on `/login`. React sends them to
`POST /auth/login` and uses the access JWT from the response to fetch
`GET /auth/me` before opening `/account`. Sign-out sends the refresh JWT to
`POST /auth/logout` so Flask can revoke the session even if the access JWT
has expired. Tokens stay in memory and are not refreshed automatically.
Reloading requires signing in again.

## Structure

- `src/app/` sets up React Router and registers pages. `/login` is public;
  `/account` is behind `RequireAuth`. Unknown routes show a not-found page.
- `src/features/` owns pages, API calls, and state for each feature. Auth owns
  the in-memory session and exposes `useAuth()` for the user and access token.
  The refresh token stays inside the auth feature.
- `src/shared/api/` provides `requestJson` for calls to Flask, including common
  timeouts, cancellation, and HTTP errors. Feature modules define their own
  request and response types.

For a new feature, create a folder under `src/features/` and register its page
in `src/app/AppRoutes.tsx`. Add authenticated pages under `RequireAuth` so a
signed-out visitor returns to the requested page after signing in. Keep state
in the feature until more than one feature needs it.

## Checks and deployment

Run `npm --prefix frontend test` for auth and redirect tests and
`npm --prefix frontend run build` to type-check and build. For deployment,
serve `frontend/dist`, serve its `index.html` for client-side routes, and proxy
`/api/*` to Flask with the `/api` prefix removed.
