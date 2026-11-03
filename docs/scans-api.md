# Scan API

All endpoints require an access token and return only the authenticated user's data.

| Method | URL | Purpose |
| --- | --- | --- |
| POST | `/scans` | Queue a scan; return `202` and its `Location` |
| GET | `/scans` | List past requests, newest first |
| GET | `/scans/<id>` | Status and completed report |
| GET | `/scans/history?target=<ip>` | Chronological reports and consecutive changes |

Submit an authorized IPv4 address or hostname and ports:

```json
{"target": "scan.example.com", "ports": [22, 80, 443]}
```

The submitted IP defines the scan scope. No destinations need to be configured
in the environment. TCP accepts IPv4 addresses and hostnames; URLs and IPv6 are
not supported. Hostnames are normalized to lowercase ASCII/IDNA without a final dot.
Unicode names that cannot round-trip without changing names require ASCII punycode.
Optional options: `timeout`, `concurrency`, `rate_limit`, and `scanners: ["tcp"]`.

The worker resolves DNS A records once at execution (5-second deadline), then
scans the fixed IPv4 set sequentially with bounded per-port concurrency and rate.
More than 8 distinct IPs fails the job rather than silently truncating results.
DNS failures mark jobs failed without fabricating port states. A records come
from the configured DNS resolver, not OS hosts files or mDNS.

New reports use schema version 2: `target` preserves the normalized requested
name; `resolved_ips` lists scanned destinations; each TCP result's `target` is
its actual IP. Counts summarize IP/port checks. Existing IPv4 reports retain their
stored schema version and remain readable. Apply migration `35ae702d91c4` before
starting the updated API/worker. It backfills old result IPs; downgrade refuses
to discard hostname or multi-address evidence.

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

History groups runs by normalized submitted target. Items contain a report,
`baseline_id`, `changes`, `only_in_previous`, `only_in_current`,
`addresses_added`, `addresses_removed`, and `configuration_changed`.
Changes compare the same IP and port; changes and unmatched observations include
`ip_address` and `port`. A DNS address change is not a closed-port observation.
Consecutive comparisons continue
across pages; a baseline may precede the requested date range. Only completed
runs contribute observations. Missing ports mean not scanned; transitions
involving `unknown` are inconclusive. Configuration differences can affect
results. Port changes do not prove a vulnerability appeared or was resolved.
