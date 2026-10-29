# AGENTS.md — Kowalski

## 1. Project Identity

**Project Name:** Kowalski  
**Category:** Cybersecurity / Network Reconnaissance / Vulnerability Assessment  
**Primary Language:** Python  
**Development Stage:** Early Development  
**Architecture:** Modular, asynchronous, extensible

### Project Vision

Kowalski is an open-source, Python-based cybersecurity tool designed to discover, analyze, and assess the attack surface of IP addresses, domains, and web applications.

The tool combines network reconnaissance, port scanning, service detection, web security analysis, and vulnerability assessment into a unified platform.

Kowalski aims to help penetration testers, security researchers, and developers understand the potential security weaknesses of systems they are authorized to assess.

The long-term goal is to build a powerful, modular security scanning platform inspired by tools such as Nmap, Nuclei, and Nessus, while implementing core functionality independently.

**Kowalski is not intended to be a simple wrapper around existing security tools.**

Core scanning, protocol analysis, and vulnerability detection should be implemented in Python whenever technically reasonable and educationally valuable.

---

## 2. Development Philosophy

Kowalski is both a cybersecurity product and a hands-on learning project.

The developer has a background in Python backend engineering and is using this project to develop practical penetration testing and offensive security knowledge.

The project must balance:

- Real cybersecurity functionality
- Clean software architecture
- Practical Python engineering
- Understanding network protocols
- Extensibility and maintainability
- Testability and reliability
- Incremental development
- Safe and authorized security testing

### Core Principles

1. **Understand before implementing.** Explain unfamiliar security concepts and technical decisions.
2. **Build incrementally.** Prefer small, functional milestones.
3. **Keep the architecture modular.** Components should be independently testable.
4. **Prefer native implementations.** Avoid relying on external scanning executables for core features.
5. **Avoid unnecessary complexity.** Do not introduce abstractions without clear benefits.
6. **Write production-quality Python.** Use clear naming, typing, validation, and error handling.
7. **Design for extensibility.** New scanning capabilities should integrate cleanly.
8. **Test important behavior.** Especially asynchronous networking and error handling.
9. **Separate evidence from conclusions.** Report findings accurately and avoid unsupported vulnerability claims.
10. **Prioritize learning.** Explain why security checks work and what limitations they have.

---

## 3. Main Capabilities

### 3.1 Target Management

Kowalski should accept:

- IPv4 addresses
- IPv6 addresses
- Domain names
- HTTP and HTTPS URLs
- IP ranges and CIDR notation in later phases

Target management should support:

- Input validation
- DNS resolution
- URL normalization
- Explicit scan scope
- Configurable scan options
- Safe handling of invalid inputs
- Detection of out-of-scope redirects
- Protection against DNS rebinding and unexpected target changes

All active scanning must remain within an explicitly authorized scope.

### 3.2 Network Port Scanning

Implement an asynchronous TCP scanning engine using Python.

Core functionality:

- Scan user-defined TCP ports and port ranges
- Detect reachable TCP services
- Distinguish between open and closed ports when possible
- Report unknown or filtered states accurately
- Support configurable timeouts
- Support concurrency limits
- Collect scan statistics
- Record errors without crashing the entire scan
- Produce structured scanning results

Later enhancements:

- Service fingerprinting
- Protocol-aware banner collection
- Common service identification
- Advanced TCP scanning techniques
- Optional UDP scanning
- Optional comparison against Nmap results

Initially, prefer `asyncio` and Python's networking libraries.

A successful TCP connection confirms that a port is accepting connections, but does not automatically prove the identity of the service or the presence of a vulnerability.

### 3.3 DNS Reconnaissance

Provide DNS inspection capabilities.

Potential features:

- A and AAAA records
- MX records
- NS records
- TXT records
- CNAME records
- DNS resolution failures
- DNS configuration observations
- Subdomain inventory from explicitly supplied or authorized sources

Avoid uncontrolled domain enumeration in the initial MVP.

### 3.4 HTTP and HTTPS Analysis

Implement a web inspection engine.

Core functionality:

- HTTP response status inspection
- Redirect analysis
- HTTP response headers
- Security header checks
- Cookie security analysis
- HTTP method inspection when safe
- Web server identification
- Technology fingerprinting with confidence levels
- TLS certificate inspection
- TLS certificate expiration checks
- Basic TLS configuration analysis
- robots.txt inspection
- sitemap.xml inspection
- Information disclosure detection

The engine should distinguish between actual security weaknesses, informational observations, and conditions requiring manual verification.

### 3.5 Vulnerability Assessment

Develop a modular vulnerability-checking framework.

Initial checks may include:

- Missing HTTP security headers
- Expired TLS certificates
- Weak TLS protocol configurations
- Risky exposed network services
- Potentially sensitive administrative interfaces
- Information disclosure
- Unsafe cookie attributes
- Security misconfigurations
- Potentially outdated software versions

Later capabilities:

- CVE intelligence integration
- CVSS score correlation
- Version-based vulnerability matching
- Technology-specific checks
- Rule-based vulnerability signatures
- Controlled vulnerability verification

A CVE match based only on an uncertain product version must be labeled as a potential finding, not a confirmed vulnerability.

Every security finding should provide supporting evidence and a clearly explained confidence level.

### 3.6 Plugin-Based Scanning Engine

Kowalski must support independently developed scanning and analysis modules.

Example components:

- TCPPortScanner
- DNSAnalyzer
- HTTPAnalyzer
- TLSAnalyzer
- SSHAnalyzer
- SecurityHeadersCheck
- ExposedServicesCheck
- CVEAnalyzer

Plugin responsibilities:

- Define the capabilities they provide
- Accept validated targets and configuration
- Respect scan scope and safety limits
- Return structured results
- Handle expected errors gracefully
- Support independent testing

The orchestration layer should remain independent of individual vulnerability checks.

Use abstract base classes or protocols when justified by multiple implementations.

Avoid creating a complicated plugin framework before it is needed.

### 3.7 Security Findings

Represent findings using a consistent data model.

Recommended fields:

- Unique finding identifier
- Target
- Affected hostname or IP address
- Affected port or URL
- Check identifier
- Finding title
- Description
- Severity
- Confidence
- Classification: observation, potential vulnerability, or confirmed vulnerability
- Supporting evidence
- Remediation guidance
- References
- Detection timestamp

Severity and confidence are separate concepts.

High severity does not necessarily mean high confidence.

Findings must be reproducible when possible.

### 3.8 Reporting

Initial output format:

- JSON

Later output formats:

- Human-readable CLI
- HTML
- PDF

Reports should include:

- Target details
- Scan configuration
- Scan start and completion timestamps
- Discovered services
- Port scan results
- Web inspection results
- Identified security findings
- Evidence
- Severity and confidence
- Remediation recommendations
- Scan limitations and errors

### 3.9 Scan Persistence and History

Later development stages should support:

- PostgreSQL storage
- Scan records
- Asset inventory
- Historical findings
- Scan-to-scan comparisons
- Newly exposed ports
- Removed services
- New security findings
- Resolved findings
- Security posture trends

Do not add database persistence until the scanning engine produces reliable structured output.

---

## 4. Preferred Technology Stack

### Core

- Python 3.12+
- asyncio
- socket
- ssl
- ipaddress
- dataclasses or Pydantic

### Networking and Web

- HTTPX
- dnspython
- Scapy when low-level packet manipulation is required

### Backend — Future Phase

- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- Background task processing if required

### Development and Testing

- pytest
- pytest-asyncio
- Ruff
- mypy where practical
- Docker
- Docker Compose
- GitHub Actions

### Frontend — Future Phase

- React
- TypeScript

Do not introduce technologies solely because they are popular.

Use the simplest dependency that correctly solves the problem.

---

## 5. Architecture Guidelines

Kowalski should follow a modular architecture with clear separation between:

1. Target parsing and validation
2. Scope management
3. Scan orchestration
4. Network scanning
5. Protocol analysis
6. Vulnerability checks
7. Finding generation
8. Reporting
9. Persistence
10. User interfaces

### Suggested Project Structure

```text
kowalski/
├── src/
│   └── kowalski/
│       ├── __init__.py
│       ├── cli.py
│       ├── core/
│       │   ├── models.py
│       │   ├── scope.py
│       │   ├── orchestrator.py
│       │   └── config.py
│       ├── scanners/
│       │   ├── base.py
│       │   ├── tcp.py
│       │   ├── dns.py
│       │   └── http.py
│       ├── analyzers/
│       │   ├── tls.py
│       │   ├── services.py
│       │   └── technologies.py
│       ├── checks/
│       │   ├── base.py
│       │   ├── headers.py
│       │   ├── tls_config.py
│       │   └── exposed_services.py
│       ├── intelligence/
│       │   └── cve.py
│       └── reporting/
│           └── json_report.py
├── tests/
│   ├── unit/
│   └── integration/
├── lab/
├── docs/
├── pyproject.toml
├── README.md
└── AGENTS.md
```

This structure is a starting point, not a mandatory final design.

Codex should adapt it to the actual state of the repository.

Do not create empty modules, placeholder interfaces, or unnecessary directories merely to match the proposed structure.

---

## 6. Async Programming Requirements

Network scanning involves significant I/O concurrency.

Prefer asynchronous I/O over unnecessary threads.

Use:

- `asyncio`
- Connection timeouts
- Bounded concurrency
- Semaphores
- Structured cancellation handling
- Explicit resource cleanup

Requirements:

- Avoid unbounded task creation.
- Ensure sockets and connections are closed.
- Handle cancellation correctly.
- Avoid blocking the event loop.
- Do not swallow unexpected exceptions.
- Handle unreachable hosts and network timeouts gracefully.
- Respect configured request limits.

Performance optimizations should be based on measured bottlenecks.

---

## 7. Safety and Authorization

Kowalski is intended exclusively for authorized security assessment and controlled learning environments.

Security requirements:

- Require an explicitly defined scanning scope.
- Reject out-of-scope targets.
- Revalidate scope after DNS resolution.
- Validate each destination IP address before connecting.
- Prevent redirects to unauthorized destinations.
- Apply configurable rate limits and timeouts.
- Limit network concurrency.
- Use non-destructive checks by default.
- Avoid credential guessing, persistence, stealth, or destructive exploitation.
- Do not automatically follow newly discovered assets outside the approved scope.

Local development should favor:

- Docker-based test environments
- Loopback interfaces
- Private virtual networks
- Intentionally vulnerable training applications
- Mock network services

Tests must not unexpectedly contact public infrastructure.

---

## 8. Coding Standards

### Python Quality

- Use descriptive names.
- Use type hints for public functions and methods.
- Prefer small functions with clear responsibilities.
- Avoid duplicated logic.
- Use Python's standard library when sufficient.
- Prefer composition over inheritance.
- Avoid global mutable state.
- Avoid premature optimization.
- Keep networking logic separate from presentation logic.
- Use structured logging rather than scattered print statements.

### Error Handling

Handle expected errors explicitly, including:

- DNS resolution failures
- Connection refusal
- Network timeouts
- TLS handshake failures
- Malformed HTTP responses
- Invalid targets
- Out-of-scope destinations
- Incomplete scan results

Do not classify all network failures as closed ports.

Unknown and timed-out states must be represented accurately.

### Testing

For every meaningful feature:

- Add unit tests.
- Add integration tests where appropriate.
- Cover edge cases.
- Test failure and timeout behavior.
- Test scope restrictions.
- Test asynchronous cancellation where relevant.

Use local mock services and controlled fixtures rather than depending on public internet services.

---

## 9. Agent Working Instructions

When working inside this repository, Codex must follow these rules.

### Before Making Changes

1. Inspect the relevant files.
2. Understand the existing architecture.
3. Check whether similar functionality already exists.
4. Identify affected modules and tests.
5. Prefer extending existing functionality over duplicating it.
6. Explain significant architectural changes before implementing them.

### During Implementation

1. Make focused, incremental changes.
2. Follow the existing project conventions.
3. Keep interfaces consistent.
4. Avoid unnecessary dependencies.
5. Add appropriate tests.
6. Preserve existing behavior unless the task requires changing it.
7. Avoid unrelated refactoring.
8. Do not add speculative features.
9. Do not introduce unnecessary abstraction layers.
10. Treat external network responses as untrusted input.

### After Implementation

1. Run relevant tests.
2. Run available linting and type checks.
3. Explain what changed.
4. Explain why the implementation was chosen.
5. Identify important limitations.
6. Describe how to verify the functionality.
7. Suggest the next logical development step.

Do not claim tests passed unless they were actually executed.

---

## 10. Mentorship Expectations

Codex is expected to act as both a software engineering partner and a cybersecurity mentor.

When introducing a new security feature, explain:

- What the feature does
- The relevant network protocol or security concept
- Why the behavior matters for penetration testing
- How the scanner detects it
- What constitutes reliable evidence
- Common false positives or limitations
- How the implementation could be improved

Explanations should be technically accurate, concise, and practical.

Assume the developer understands Python backend engineering but is actively learning cybersecurity internals.

Do not overexplain basic Python concepts unless requested.

---

## 11. Development Roadmap

### Milestone 1 — Functional TCP Scanner

Objective: Build a working asynchronous TCP port scanner.

Deliverables:

- CLI entry point
- IPv4 target validation
- Explicit scope configuration
- Configurable TCP port selection
- Asynchronous connection attempts
- Bounded concurrency
- Connection timeouts
- Structured port results
- JSON report generation
- Unit tests
- Local integration test environment

Example CLI:

```bash
kowalski scan 192.168.56.10 --ports 1-1000
```

Example output:

```json
{
  "target": "192.168.56.10",
  "scan_type": "tcp_connect",
  "ports": [
    {
      "port": 22,
      "state": "open"
    },
    {
      "port": 80,
      "state": "closed"
    },
    {
      "port": 443,
      "state": "unknown"
    }
  ]
}
```

The example output is illustrative.

A TCP connect scanner should only report states supported by observed connection behavior.

### Milestone 2 — Service and DNS Analysis

- Service banner collection
- Protocol-aware identification
- DNS resolution
- Domain scanning
- Hostname support

### Milestone 3 — Web Inspection

- HTTP probing
- Security headers
- Redirect inspection
- Cookies
- TLS certificates
- Basic technology identification

### Milestone 4 — Vulnerability Engine

- Modular security checks
- Standardized findings
- Severity and confidence classification
- Evidence storage
- Remediation guidance

### Milestone 5 — Security Platform

- FastAPI
- Persistent scan storage
- Background jobs
- Scan history
- Dashboard
- Historical comparison

### Milestone 6 — Advanced Capabilities

- CVE intelligence
- Asset mapping
- Extended protocol analysis
- Configurable scanning profiles
- Scheduled scanning
- Advanced reporting

---

## 12. Definition of Done

A feature is considered complete when:

1. It performs its intended function.
2. It handles relevant failure conditions.
3. It respects target scope and safety constraints.
4. It has appropriate automated test coverage.
5. It uses consistent data models.
6. It follows project coding standards.
7. Its limitations are documented.
8. It does not unnecessarily increase architectural complexity.

---

## 13. Current Priorities

Prioritize the following in order:

1. Reliable core functionality
2. Correct network behavior
3. Target-scope safety
4. Code clarity
5. Test coverage
6. Extensibility
7. Performance
8. Additional features
9. User interface

**Do not prioritize dashboard development over the core scanning engine.**

**Do not build an entire vulnerability management platform before the initial scanning capabilities are stable.**

---

## 14. Long-Term Direction

Kowalski should evolve from a simple asynchronous TCP scanner into a comprehensive, modular security assessment tool.

The long-term vision includes:

- Network reconnaissance
- Web attack surface discovery
- Service and technology fingerprinting
- Vulnerability intelligence
- Security misconfiguration analysis
- Historical attack surface monitoring
- Professional vulnerability reporting
- Extensible custom security checks

Every significant architectural decision should support this direction without overengineering the present implementation.

**Final instruction to Codex:**

Treat this document as the project's persistent engineering context.

Always inspect the current repository before recommending or implementing changes.

Follow the principles above while adapting to the actual codebase.

Build Kowalski incrementally, favor correctness over complexity, and help the developer understand both the Python implementation and the cybersecurity concepts behind it.