# Engine

- `TCPPortScanner`: async TCP connect scanning with required IPv4 allowlist and ports.
- `ScannerService.run_all()`: collects results from available scanners (TCP only).
- Defaults per scan: 1-second timeout, 20 workers, 100 connection starts/second.
- Results: `open` (accepted), `closed` (refused), `unknown` (timeout or OS error).
- Sockets close on completion or cancellation; cancellation propagates.

Open ports do not prove vulnerabilities. DNS, IPv6, and service detection are
not implemented. The CLI still uses simulated results.

Run local tests:

```bash
uv run pytest tests/test_tcp_scanner.py tests/test_scanner_service.py
```
