# Kowalski frontend

A React and TypeScript client for the Flask API, with registration, sign-in,
profile, and a dark workspace with an overview, scans, target history, and report details.

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
`GET /auth/me` before opening `/dashboard` (or the protected page you requested). Sign-out in the navbar sends the
refresh JWT to `POST /auth/logout` so Flask can revoke the session even if the
access JWT has expired. Protected requests refresh an expired access JWT once
through `/auth/refresh`; concurrent requests share that refresh. A rejected
refresh returns you to sign-in. Tokens stay in memory, so reloading still
requires signing in again.

## Scans

Open **Scans** in the navbar or `/scans`. Enter one authorized IPv4 address or
hostname. Ports start empty: choose a web, remote-access, or common TCP preset,
or enter custom ports and ranges such as `22,80,8000-8010` (at most 1024 ports).
Collapsed advanced settings explain timeout, concurrency, and rate limit.
SSH identification uses the backend default, with no separate control.

Apply migrations and run the API worker alongside Flask:

```bash
uv run flask --app run.py db upgrade
uv run flask --app run.py scan-worker
```

`/dashboard` is the landing page: it shows recent activity and the latest scan.
Activity counts cover only the latest loaded requests, not lifetime totals.
The compact form stays visible on `/scans`. Results are expandable below the
scan list. Top navigation links to Overview, Scans, Target history, and Profile.
The UI uses a dark theme with a muted blue accent and no logo.

Submission queues a job. Its status and results appear in the selected-scan
section below the list; the run is retained as `/scans?run=<id>`. It polls every two seconds after
each response until completion or failure. Navigating away or signing out
stops polling, not the backend job. If a status request fails, use **Retry status
check**. No timeout or lost submission response is automatically retried; check
**Past scans** before submitting again if the outcome is uncertain.

Results show IP, port, state, and identified service. Unknown is not closed;
an advertised service is not a confirmed vulnerability. **Past scans** lists
owned requests, newest first, with **View**, **Load more**, and a refresh button.
The selected run's status updates in that list as it is polled. Other rows can
be refreshed manually. Filter the list by exact target, status, and date range.
Filters apply server-side and persist in the URL. Calendar dates use your browser's
local timezone and include the entire end date. Changing filters resets pagination.

Results are sorted numerically by port, then IP address. **Report details** opens
`/scans/<id>/report`, with timestamps, connection evidence, SSH banners, confidence,
received bytes (control bytes escaped), and scan configuration.

### Target history

Open **Target history** or follow **View target history** from a completed scan.
The separate `/history?target=<target>` page shows all completed runs, newest first,
with changed runs highlighted. Expand a run to see differences from its older
chronological predecessor: TCP states, SSH evidence, address coverage, and ports
observed in only one run. The oldest run is the baseline. Unknown and missing
observations are never treated as proof of closure or vulnerability removal.

**Load earlier scans** appends ten older runs at a time, preserving comparisons
across pages. Changing targets or refreshing resets pagination. **View this run**
returns to its result on the Scans page.

## Structure

- `src/app/` sets up React Router and registers pages. `/login` and `/register`
  are public. `RequireAuth` and `WorkspaceLayout` protect the workspace pages
  and provide their top navigation. `/account` redirects to `/profile`; unknown routes show a not-found page.
- `src/features/` owns pages, API calls, and state for each feature. Auth owns
  the in-memory session. `useAuth().request` handles protected calls and JWT
  refresh. The refresh token stays inside the auth feature. Scans own their
  form, filters, API types, polling, and pagination under `src/features/scans/`.
  `ScansPage` coordinates selection; `ScanForm`, `PastScansPanel`, and
  `TargetHistoryPanel` own their respective views. History interpretation stays
  separate from rendering in `historyDifferences.ts`. Overview lives under
  `src/features/overview/`. See the [design decisions](../docs/frontend-design.md).
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
