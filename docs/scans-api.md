# Scan API

All endpoints require an access token and return only the authenticated user's data.

| Method | URL | Purpose |
| --- | --- | --- |
| POST | `/scans` | Queue a scan; return `202` and its `Location` |
| GET | `/scans` | List past requests, newest first |
| GET | `/scans/<id>` | Status and completed report |
| GET | `/scans/history?target=<ip>` | Chronological reports and consecutive changes |

Submit an authorized IPv4 target and ports:

```json
{"target": "93.184.216.34", "ports": [22, 80, 443]}
```

The submitted IP defines the scan scope. No destinations need to be configured
in the environment. Only TCP and literal IPv4 addresses are supported currently.
Optional options: `timeout`, `concurrency`, `rate_limit`, and `scanners: ["tcp"]`.

## Run

Apply migrations, then start the API and worker in separate terminals:

```bash
uv run flask --app run.py db upgrade
uv run flask --app run.py run
uv run flask --app run.py scan-worker
```

Compose starts the worker automatically. In containers, localhost means the
worker container. The existing scanner CLI remains independent of API storage.

The database holds queued/running/completed/failed jobs. PostgreSQL coordinates
one active scan at a time across worker processes. If a worker stops, the next
worker marks abandoned running jobs failed. SQLite is for single-process tests.

Resource defaults are in `app/config.py`: 1024 ports, timeout up to 5 seconds,
20 concurrent connections, 100 attempts/second, 5 pending jobs/user, 100 pending
jobs overall, and a 300-second job deadline. They are limits, not target lists.
If execution or storage fails, the job is failed; no partial report is committed.
There are no automatic retries, cancellation, or deletion endpoints yet.

## History

Lists accept `target`, `status`, `limit` (1–100), and `cursor`. History requires
`target`, with optional timezone-aware ISO `from`/`to`, `limit`, and `cursor`.
Pass `next_cursor` unchanged as an encoded query value, retaining the filters.

History items contain a report, `baseline_id`, `changes`, `only_in_previous`,
`only_in_current`, and `configuration_changed`. Consecutive comparisons continue
across pages; a baseline may precede the requested date range. Only completed
runs contribute observations. Missing ports mean not scanned; transitions
involving `unknown` are inconclusive. Configuration differences can affect
results. Port changes do not prove a vulnerability appeared or was resolved.
