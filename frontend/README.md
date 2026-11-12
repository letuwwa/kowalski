# Kowalski frontend

A React and TypeScript client for the Flask API, with registration, sign-in,
profile, and a scan dashboard with results, past scans, and target differences.

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

## Accounts

Use an existing account or open `/register` to create one. The form calls
`POST /auth/register`, shows validation errors from Flask, and signs you in
with the returned JWTs. `/profile` displays your name, username, and email.

Enter the email or username and password on `/login`. React sends them to
`POST /auth/login` and uses the access JWT from the response to fetch
`GET /auth/me` before opening `/profile`. Sign-out in the navbar sends the
refresh JWT to `POST /auth/logout` so Flask can revoke the session even if the
access JWT has expired. Protected requests refresh an expired access JWT once
through `/auth/refresh`; concurrent requests share that refresh. A rejected
refresh returns you to sign-in. Tokens stay in memory, so reloading still
requires signing in again.

## Scans

Open **Scan** in the navbar or `/scans`. Enter one authorized IPv4 address or
hostname. Ports start empty: choose a web, remote-access, or common TCP preset,
or enter custom ports and ranges such as `22,80,8000-8010` (at most 1024 ports).
Collapsed advanced settings explain timeout, concurrency, and rate limit.
SSH identification uses the backend default, with no separate control.

Apply migrations and run the API worker alongside Flask:

```bash
uv run flask --app run.py db upgrade
uv run flask --app run.py scan-worker
```

The dashboard separates the new-scan form, selected result, target history,
and past requests into panels. Selected results include counts of TCP checks,
open, closed, and unknown states. Panels stack on smaller screens.

Submission queues a job. Its status and results appear in the selected-scan
panel; the run is retained as `/scans?run=<id>`. It polls every two seconds after
each response until completion or failure. Navigating away or signing out
stops polling, not the backend job. If a status request fails, use **Retry status
check**. No timeout or lost submission response is automatically retried; check
**Past scans** before submitting again if the outcome is uncertain.

Results show IP, port, state, and identified service. Unknown is not closed;
an advertised service is not a confirmed vulnerability. **Past scans** lists
owned requests, newest first, with **View**, **Load more**, and a refresh button.
The selected run's status updates in that list as it is polled. Other rows can
be refreshed manually.

### Target history

Selecting a scan opens that target's history. You can also enter another IPv4
address or hostname in the **Target history** panel. The target is retained as
a `target` URL parameter, independently of the selected result.

The panel calls `/scans/history`, displaying completed runs in chronological
order. Expand a run to see its differences from the preceding completed run:
TCP states, SSH banner evidence, address coverage, and ports observed in only
one run. The first run is a baseline. Configuration changes are called out;
unknown states and missing evidence never imply closure or vulnerability removal.

**Load later scans** appends ten runs at a time, preserving comparisons across
pages. Changing targets or refreshing starts from the first page. The history
refreshes when the selected scan completes. **View this run** opens its report
in the selected-scan panel.

## Structure

- `src/app/` sets up React Router and registers pages. `/login` and `/register`
  are public. `RequireAuth` and `WorkspaceLayout` protect `/profile` and `/scans`, giving them
  the navbar. `/account` redirects to `/profile`; unknown routes show a not-found page.
- `src/features/` owns pages, API calls, and state for each feature. Auth owns
  the in-memory session. `useAuth().request` handles protected calls and JWT
  refresh. The refresh token stays inside the auth feature. Scans own their
  form, API types, polling, and pagination under `src/features/scans/`.
  `ScansPage` coordinates selection; `ScanForm`, `PastScansPanel`, and
  `TargetHistoryPanel` own their respective views. History interpretation stays
  separate from rendering in `historyDifferences.ts`.
- `src/shared/api/` provides `requestJson` for calls to Flask, including common
  timeouts, cancellation, and HTTP errors. Feature modules define their own
  request and response types.

For a new feature, create a folder under `src/features/` and register its page
in `src/app/AppRoutes.tsx`. Add authenticated pages under `WorkspaceLayout` so
they get the navbar and signed-out visitors return after signing in. Keep state
in the feature until more than one feature needs it.

## Checks and deployment

Run `npm --prefix frontend test` for auth, redirect, scan, and polling tests and
`npm --prefix frontend run build` to type-check and build. For deployment,
serve `frontend/dist`, serve its `index.html` for client-side routes, and proxy
`/api/*` to Flask with the `/api` prefix removed.
