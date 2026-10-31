# Report persistence and scan history

Status: models, TCP persistence, API endpoints, worker jobs, and chronological
history are implemented. See [API usage](scans-api.md). Frontend views remain planned.

## Agreed scope

- Persistence and history belong to the authenticated API/frontend only.
- The CLI continues to produce terminal or JSON output without database features.
- Keep the engine independent of Flask, authentication, and SQLAlchemy.
- The API coordinates scanning and storage; the frontend presents history.

```text
Frontend → authenticated API → ScannerService → ScanReport
                            → persistence layer → PostgreSQL
```

## Storage models

SQLAlchemy models in `app/models/` define reports and API jobs:

| Table | Fields |
| --- | --- |
| `scan_runs` | Report UUID, user ID, target, start/end timestamps, configuration JSON, report schema version |
| `tcp_port_results` | Scan ID, port, state, evidence, OS error number |
| `scan_jobs` | Owner, target, configuration, status, timestamps, error, report reference |

Each run belongs to one user and has many port results. Enforce uniqueness on
`(scan_id, port)`. Derive ownership from the authenticated user, never a supplied
user ID; restrict history and report access to the owner.

`ScanRun` requires the original report UUID. Port/state and timestamp checks
are enforced by the database. An owner/time/UUID index supports history queries.
Deleting a run cascades to its results; deleting an owner with history is
restricted. Results are observations, not vulnerability claims.

Save a completed run and its results in one transaction. Preserve each run as a
snapshot; later scans create new records. Handle repeated saves of the same
report UUID without duplicating results. A storage failure rolls back the report
and marks the job failed; recovery/retry behavior is deferred.

`engine/report.py` already provides UUIDs, UTC timestamps, configuration,
evidence, and derived summary counts. `to_record()` retains native UUID/datetime
values and JSON-compatible payloads, but is not an ORM model. Map reports to
normalized rows in the persistence layer; no engine database dependency is needed.

## Execution and next steps

`POST /scans` queues work for a separate worker; PostgreSQL coordinates one active
scan globally. Jobs are queued/running/completed/failed. Completed reports and
job completion are saved atomically. Targets come from requests, not an env list.

`GET /scans` lists owned requests, `/scans/<id>` returns status/results, and
`/scans/history?target=<ip>` computes a chronological timeline. Comparisons are
between consecutive completed runs, rather than two selected versions.

Next: hostname support, then service identification, then a simple React app in
`./frontend`; see [next features](next-features.md). Retention, cancellation,
deletion, and automatic retries remain undecided; discuss them before adding behavior.

## Comparison semantics

- A port omitted from a later scan was not scanned; it is not closed.
- `open → unknown` is inconclusive, not evidence of service removal.
- Retain configuration: differing ports, timeouts, or scan locations affect results.
- The same IP at different times may represent different assets.
- Port changes do not establish that a vulnerability appeared or was resolved.

Defer scheduled scans, trend dashboards, and automatic vulnerability-resolution
claims until reliable storage and history are available.
