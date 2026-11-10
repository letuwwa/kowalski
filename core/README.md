# Scanning core

`core` contains the scanning and reporting code shared by the Flask worker
and `cli`. Typer and Rich are used by the CLI only.

- `core.services.tcp.TCPPortScanner`: async IPv4 TCP scanning with explicit scope,
  timeouts, concurrency and rate limits, and socket cleanup.
- `core.services.ScannerService.run_all()`: returns a completed `ScanReport` containing
  the normalized IPv4/hostname target, resolved IPs, configuration, timestamps,
  and per-IP results (currently `tcp`).
- `core.targets.resolve_ipv4()`: bounded DNS A resolution using [dnspython's async
  resolver](https://dnspython.readthedocs.io/en/stable/async-resolver-functions.html).
  Resolves once per run (5 seconds, at most 8 IPs); numeric destinations stay fixed.
- `core.services.ssh.identify_ssh()`: receive-only SSH banner identification on selected
  open ports (default 22). Reuses pinned IPs and the TCP timeout/rate limit; probes
  run sequentially with at most 4 KiB read per connection.
- `core.report.ScanReport`: UUID identity, UTC timestamps, evidence, and derived counts.
  `to_dict()` / `to_json()` produce JSON-compatible output; `to_record()` retains
  native UUID/datetime values for future SQLAlchemy Uuid/DateTime columns and
  nested JSON payloads. It performs no database writes.

Failed or cancelled scans do not return a completed report. Connection timeouts
are reported as `unknown`; an open port alone does not prove a vulnerability.

Run the CLI:

```bash
uv run python -m cli.scan 127.0.0.1 --allow-ip 127.0.0.1 --ports 22,5432,8000-8010
uv run python -m cli.scan scan.example.com --allow-target scan.example.com --ports 443
```

Add `--format json` for reports. See the [project README](../README.md) for
options and limitations. Engine code does not depend on Flask or a database.

Run the scanning and reporting tests with `uv run pytest tests/core`.
Run the terminal interface tests with `uv run pytest tests/cli`.
