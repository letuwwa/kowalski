# HTTP/HTTPS service identification — planned

Status: documentation only. The current engine identifies SSH; HTTP/HTTPS probes
are not implemented. Frontend CI is deferred for now.

## Purpose

An open TCP port proves that a connection was accepted. It does not prove that
HTTP is running, even on port 80 or 443. The next milestone will recognize web
services from an actual HTTP response and retain the evidence in scan reports.
This helps inventory web-facing services before later security checks.

## Proposed behavior

1. Run the existing TCP scan first. Probe only explicitly selected ports observed
   as open, using the same resolved IPv4 snapshot and rechecking destination scope.
2. Send one `HEAD / HTTP/1.1` request. HEAD asks for response metadata without a
   response body. Include the original normalized target in `Host`, with the port
   when non-default, so hostname-based virtual hosts receive the correct request.
3. For HTTPS, establish TLS first, using the original hostname for server-name
   indication (SNI) and certificate identity verification, while connecting to the
   pinned IP. Keep certificate verification enabled; no insecure retry.
4. Parse a complete, valid HTTP/1.0 or HTTP/1.1 response header block. Collect
   status, optional advertised `Server`, optional redirect `Location`, protocol,
   and bounded raw response evidence. Record successful TLS establishment when
   applicable. A valid 404 or 405 still identifies HTTP.
5. Record redirect destinations without following them. Do not fetch page bodies,
   retry with GET, send credentials, or probe additional discovered destinations.

Suggested defaults are HTTP on 80/8080 and HTTPS on 443/8443, intersected with the
user's TCP port selection. Allow alternate ports and disabling each probe type.
Before implementation, settle option names, overlapping SSH/HTTP/HTTPS selections,
exact limits, and how the frontend exposes these options. Do not silently guess a
protocol from a port number or add ports to a scan.

## Reliability and evidence

Use one overall timeout per probe covering connection, TLS, request, and response;
bound received bytes and probe concurrency, respect the connection rate limit,
and close resources on success, failure, and cancellation. A proposed header cap
is 16 KiB. Preserve partial evidence on timeout or malformed responses.

Protocol recognition can have high confidence when supported by a valid response.
The `Server` header is optional, self-reported, and may describe a proxy. It is not
proof of product identity, version, or vulnerability. A timeout, malformed reply,
HEAD incompatibility, or rejected certificate leaves identification inconclusive;
none changes the earlier TCP observation to closed. An IP-only scan may see a
default virtual host. HTTP/2-only services are outside this initial milestone.

Certificate verification failure is a probe error, not a complete TLS assessment.
Certificate inventory, expiry checks, security headers, cookies, technology
fingerprinting, and CVE matching remain separate future features.

## Implementation plan for a later session

- Add an independent async HTTP/HTTPS identifier under `core/services/` using
  Python networking and TLS libraries; extend orchestration alongside SSH.
- Extend structured observations and configuration while preserving older reports
  and queued jobs. Review schema/version compatibility before changing fields.
- Carry explicit options through CLI, API validation, and workers; persist through
  the existing report adapter. Review whether a migration is actually necessary.
- Present protocol/status/evidence in existing results and report details. Extend
  history comparisons for HTTP metadata without treating absent evidence as
  service removal or making vulnerability claims.
- Test with local HTTP and TLS fixtures: fragmented/malformed/oversized headers,
  redirects without follow-up connections, missing Server, valid error statuses,
  trusted/untrusted certificates, SNI/Host, pinned IPs, scope rejection, timeouts,
  cancellation cleanup, persistence, legacy reports, and history differences.

## Concepts to learn

HTTP request/response syntax and HEAD semantics; virtual hosting and Host headers;
TLS handshakes, certificate trust and SNI; DNS pinning; bounded asynchronous I/O;
and the difference between observed protocol evidence and inferred software identity.

References: [HTTP/1.1 message syntax](https://www.rfc-editor.org/rfc/rfc9112.html),
[HEAD semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.2), and
[Python TLS verification](https://docs.python.org/3/library/ssl.html#ssl.create_default_context).
