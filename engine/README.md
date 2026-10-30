# Engine

- `TCPPortScanner`: async TCP connect scanning with required IPv4 allowlist and ports.
- `ScannerService.run_all()`: returns a `ScanReport` (TCP only for now).
- Reports include UUID, UTC timestamps, configuration, evidence, and summary counts.
- `to_json()` exports JSON; `to_record()` preserves UUID/datetime types for future
  SQLAlchemy Uuid/DateTime columns and JSON payloads. No persistence yet.
- Defaults per scan: 1-second timeout, 20 workers, 100 connection starts/second.
- Results: `open` (accepted), `closed` (refused), `unknown` (timeout or OS error).
- Sockets close on completion or cancellation; cancellation propagates.

Open ports do not prove vulnerabilities. DNS, IPv6, and service detection are
not implemented.

Run the CLI (repeat `--allow-ip` to extend the explicit scope):

```bash
uv run python -m engine.scan 127.0.0.1 --allow-ip 127.0.0.1 --ports 22,5432,8000-8010
```

Options: `--format table|json`, `--timeout`, `--concurrency`, `--rate-limit`,
`--no-color`, `--help`. Cancelled or failed scans do not return a report.

Run local tests:

```bash
uv run pytest tests/test_tcp_scanner.py tests/test_scanner_service.py tests/test_report.py tests/test_engine_cli.py
```
