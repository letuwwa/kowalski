# Engine

- `services.tcp.TCPPortScanner`: async IPv4 TCP scanning with explicit scope,
  timeouts, concurrency and rate limits, and socket cleanup.
- `services.ScannerService.run_all()`: returns a completed `ScanReport` containing
  configuration, timestamps, and results grouped by scanner (currently `tcp`).
- `report.ScanReport`: UUID identity, UTC timestamps, evidence, and derived counts.
  `to_dict()` / `to_json()` produce JSON-compatible output; `to_record()` retains
  native UUID/datetime values for future SQLAlchemy Uuid/DateTime columns and
  nested JSON payloads. It performs no database writes.

Failed or cancelled scans do not return a completed report. Connection timeouts
are reported as `unknown`; an open port alone does not prove a vulnerability.

Run the CLI:

```bash
uv run python -m engine.scan 127.0.0.1 --allow-ip 127.0.0.1 --ports 22,5432,8000-8010
```

Add `--format json` for reports. See the [project README](../README.md) for
options and limitations. Engine code does not depend on Flask or a database.

Run local tests:

```bash
uv run pytest tests/test_tcp_scanner.py tests/test_scanner_service.py \
  tests/test_report.py tests/test_engine_cli.py
```
