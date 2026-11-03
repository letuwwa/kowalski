# SSH service identification

After TCP scanning, the engine reconnects to selected open ports and reads SSH
identification lines. Default: port 22. Alternate ports must also be part of the
TCP port selection; no extra ports are scanned automatically.

```bash
uv run python -m engine.scan 127.0.0.1 --allow-target 127.0.0.1 --ports 22,2222 --service-ports 22,2222
```

API option: `"service_ports": [22, 2222]`. Disable with `[]` in the API or
`--service-ports none` in the CLI. The report records the selected options.

The receive-only probe follows [RFC 4253 section 4.2](https://www.rfc-editor.org/rfc/rfc4253#section-4.2):
it accepts preliminary lines and fragmented TCP data, then recognizes a complete
SSH identification line (at most 255 bytes). It also recognizes legacy 1.5/1.99
identification and LF-only termination. It sends no payload, credentials, or key
exchange messages. Servers waiting for a client greeting may remain unidentified.

Limits: one overall TCP-configured timeout per probe, 4096 bytes maximum, sequential
probes with the configured connection rate bound. Probes reuse the resolved IP
snapshot and recheck destination scope. Cancellation closes sockets and propagates.
API jobs retain their existing overall deadline.

Schema version 3 reports include `services`, keyed by `ip_address` and `port`.
Each observation contains `status` (`identified`, `unidentified`, `timeout`, or
`error`), `evidence_base64` (exact bounded bytes), and optional `protocol`, `banner`,
`protocol_version`, `advertised_software`, `confidence`, and `error`.
High confidence means the identification line matches SSH syntax; the banner and
software identity are self-reported, not verified. No vulnerability is inferred.
Raw bytes use base64 to preserve binary data and terminal control characters safely.
The CLI displays parsed software and status; JSON retains the evidence.

A failed reconnect does not change the earlier TCP state. History compares
identified banners on matching IP/port pairs, including comments. A timeout or
missing observation cannot prove SSH disappeared. Changing probe selection may
change the available evidence. Other protocols and active probes remain deferred.

Apply `uv run flask --app run.py db upgrade` before starting the updated API or
worker. Observations are stored as JSON on completed reports; older reports remain
readable. Downgrade refuses to discard collected service observations.
