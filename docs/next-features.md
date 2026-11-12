# Next features

Agreed order: hostname support → service identification → simple React frontend.
This is a plan for later sessions, not authorization to implement everything now.
Keep changes incremental and discuss new behavior before expanding the scope.

## 1. Hostname support

Implemented: API, engine, and CLI accept hostnames; DNS resolves once per run
with a 5-second deadline and an 8-address cap. Reports preserve the requested
name and per-IP evidence. History groups by normalized target and compares
matching IP/port observations. Tests use controlled DNS fixtures and loopback
services. See [API usage](scans-api.md) for migration and output details.

## 2. Service identification

Implemented: bounded, receive-only SSH identification on selected open TCP ports,
with pinned IPs, raw evidence, confidence, persistence, CLI/API options, and history.
See [service identification](service-identification.md) for behavior and limits.
Discuss additional protocols and active probes before adding them.

## 3. Simple React frontend

- Implemented: [React frontend](../frontend/README.md) with registration, JWT
  sign-in/refresh, profile, and a navbar for signed-in users. `/scans` supports
  presets/custom ports, collapsed advanced options, polling, minimal results,
  and a paginated past-scans list. The dashboard includes a chronological
  target-history panel with TCP, SSH, address, and port-coverage differences.
- Possible follow-ups: past-scan filters and richer report evidence. Discuss
  scope before implementing them.
- Clearly distinguish unknown states and unscanned ports; show API validation
  errors and loading/empty states.
- Keep the UI small; defer advanced dashboards, scheduling, and extra workflows.

Current backend usage is documented in [scan API](scans-api.md).
