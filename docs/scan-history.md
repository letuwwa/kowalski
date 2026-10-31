# Report persistence and scan history

Status: SQLAlchemy models and migration implemented for completed TCP reports.
Persistence operations, API endpoints, and frontend history remain planned.

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

SQLAlchemy models in `app/models/` and migration `9b7106cd24ef` define two tables:

| Table | Fields |
| --- | --- |
| `scan_runs` | Report UUID, user ID, target, start/end timestamps, configuration JSON, report schema version |
| `tcp_port_results` | Scan ID, port, state, evidence, OS error number |

Each run belongs to one user and has many port results. Enforce uniqueness on
`(scan_id, port)`. Derive ownership from the authenticated user, never a supplied
user ID; restrict history and report access to the owner.

`ScanRun` requires the original report UUID. Port/state and timestamp checks
are enforced by the database. An owner/time/UUID index supports history queries.
Deleting a run cascades to its results; deleting an owner with history is
restricted. Results are observations, not vulnerability claims.

Save a completed run and its results in one transaction. Preserve each run as a
snapshot; later scans create new records. Handle repeated saves of the same
report UUID without duplicating results. A storage failure must be reported
without discarding the completed scan report.

`engine/report.py` already provides UUIDs, UTC timestamps, configuration,
evidence, and derived summary counts. `to_record()` retains native UUID/datetime
values and JSON-compatible payloads, but is not an ORM model. Map reports to
normalized rows in the persistence layer; no engine database dependency is needed.

## Implementation order

1. Next: save/list/retrieve operations with atomic writes and owner filtering.
   Model tests already cover constraints, evidence, UUIDs, cascade/restrict
   behavior, transaction rollback, and migration upgrade/downgrade.
2. Authenticated history endpoints with pagination and ownership tests.
3. Scan submission with explicit authorized scope and bounded execution.
4. Selected-run comparisons, then frontend history, details, and comparison views.

Decide background execution before adding scan submission: long scans should
not occupy an HTTP request. Job mechanism, lifecycle states, handling of failed
or cancelled runs, retention, and API deletion policies remain undecided.

## Comparison semantics

- A port omitted from a later scan was not scanned; it is not closed.
- `open → unknown` is inconclusive, not evidence of service removal.
- Retain configuration: differing ports, timeouts, or scan locations affect results.
- The same IP at different times may represent different assets.
- Port changes do not establish that a vulnerability appeared or was resolved.

Defer scheduled scans, trend dashboards, and automatic vulnerability-resolution
claims until reliable storage and history are available.
