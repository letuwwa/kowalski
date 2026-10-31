# Next features

Agreed order: hostname support → service identification → simple React frontend.
This is a plan for later sessions, not authorization to implement everything now.
Keep changes incremental and discuss new behavior before expanding the scope.

## 1. Hostname support

- Accept domain names alongside existing IPv4 targets in the API and engine.
- Resolve DNS asynchronously, preserve the original hostname and resolved IPs
  in reports, and connect to the validated numeric destinations.
- Keep scope tied to the submitted hostname and its validated resolution;
  do not introduce environment target allowlists or automatic asset discovery.
- Handle resolution errors and timeouts. Decide how multiple returned addresses
  are scanned and how hostname history is grouped before implementation.
- Test with controlled DNS fixtures and loopback services, not public systems.

## 2. Service identification

- Begin with bounded SSH banner collection on selected open TCP ports.
- Preserve raw evidence, detected protocol, and confidence; do not infer service
  identity from the port number alone or treat versions as confirmed vulnerabilities.
- Apply timeouts, byte limits, scope checks, concurrency limits, and cleanup.
- Test valid, partial, malformed, silent, and misleading responses locally.
- Discuss additional protocols and active probes before adding them.

## 3. Simple React frontend

- Create the application in `./frontend` after the two engine features above.
- Reuse the existing authentication and scan API.
- Start with login, scan submission, job status polling, past runs, report details,
  and a target's chronological changes.
- Clearly distinguish unknown states and unscanned ports; show API validation
  errors and loading/empty states.
- Keep the UI small; defer advanced dashboards, scheduling, and extra workflows.

Current backend usage is documented in [scan API](scans-api.md).
