# Codebase audit and stabilization report

Date: 2026-10-29

## 1. Project overview

Reviewed all first-party Python modules, the existing tests, both Alembic
revisions and migration environment, dependency metadata and lockfile, README,
environment example, Dockerfile, Compose configuration, and startup scripts.

The project is a synchronous Flask API built around an application factory.
Shared extensions provide SQLAlchemy, migrations, CORS, JWT verification, and
rate limiting. Blueprints expose database health and authentication endpoints.
Users have UUID identities, hashed passwords, an active flag, and database-backed
roles. Access and refresh tokens share a session ID; a database blocklist revokes
the complete session on logout. Scheduled request-time cleanup and a CLI command
remove expired revocations while retaining records long enough to cover access
tokens issued shortly before refresh expiry. Container startup waits for the
database, applies migrations, cleans revocations, and starts Gunicorn.

The existing pytest suite had 57 passing tests. Tests default to isolated SQLite
and support a disposable PostgreSQL database. Ruff is the configured linter and
formatter; there is no configured type checker or CI workflow.

## 2. Issues discovered

Locations below refer to the resulting working tree.

| Location | Severity | Problem and impact | Status |
| --- | --- | --- | --- |
| `app/extensions.py:71` | Medium | ORM bulk-delete synchronization evaluated timestamp comparisons in Python. Loaded SQLite records have naive timestamps, whereas cleanup cutoffs are timezone-aware. Cleanup raised `TypeError` and could fail an authenticated request or CLI operation. | Fixed: use database-based `fetch` synchronization, preserving correct ORM object state. |
| `app/extensions.py:62` | Medium | Cleanup always passed JWT decode leeway into `timedelta(seconds=...)`. The JWT stack also accepts a `timedelta`, which caused cleanup and authenticated requests to fail for that setting. | Fixed: preserve `timedelta` values and normalize numeric values. |
| `app/routers/utils/auth.py:40` | Medium | `get_json(silent=True)` does not handle the JSON decoder's `RecursionError`. A 200 KB deeply nested request, below the existing 1 MiB limit, caused registration and login to fail with a server error. | Fixed: treat decoder-depth failures like other invalid JSON, retaining registration's 400 and login's 401 responses. |
| `uv.lock:454` | High dependency risk | Locked PyJWT 2.13.0 was flagged by the vulnerability database, including malformed-token parsing and conditional key/JWKS handling weaknesses. Most key/JWKS advisories require configurations absent from this app; their exploitability here was not established. | Updated to compatible PyJWT 2.15.1; final audit clean. |
| `uv.lock:557` | Low for this deployment | Locked Werkzeug 3.1.8 was flagged for Windows NTFS device-name handling in `safe_join`. The supplied Linux deployment does not meet that advisory's prerequisites. | Updated to Werkzeug 3.1.9; final audit clean. |

The initial dependency audit reported 16 advisory entries across two packages;
entries can overlap and should not be read as 16 independently exploitable bugs
in this application. No confirmed application bug identified in this audit
remains unfixed.

## 3. Changes implemented

- Added failing regression tests before fixing all three application bugs.
- Delegated cleanup timestamp filtering to the database without changing the
  retention predicates, schema, token format, or logout behavior.
- Accepted the JWT library's existing clock-skew setting types consistently.
- Added a narrow decoder-depth exception handler. Database and unrelated
  application exceptions still propagate; no checks or tests were disabled.
- Updated only the two flagged runtime transitive dependencies in the lockfile.
- Added pytest-cov as a development dependency, enabled branch measurement,
  included all first-party Python areas, and set an 85% coverage threshold.
- Added focused validation, authentication, configuration, startup, and cleanup
  tests. The WSGI smoke test explicitly disposes its additional database engine.
- Documented coverage commands and refreshed the dependency-audit date.

No product features, API contracts, database schemas, or deployment
infrastructure were changed. The existing organization is suitable for this
small project; a broad architectural refactor was not justified.

## 4. Testing and validation

Final runtime: Python 3.14.3, PostgreSQL 18.6, and the updated locked dependencies.
The Dockerfile's Python 3.14.7 image was inspected but not built or executed.

| Check actually executed | Result |
| --- | --- |
| Baseline `.venv/bin/pytest -q` | 57 passed |
| Final `.venv/bin/pytest --cov --cov-report=term-missing -q` | 110 passed; 95.79% combined statement/branch coverage |
| Final full pytest suite with `--database-url` pointing to a fresh temporary PostgreSQL database | 110 passed |
| `.venv/bin/ruff check .` | Passed |
| `.venv/bin/ruff format --check .` | Passed |
| `sh -n docker/entrypoint.sh` | Passed |
| `docker compose config --quiet` with placeholder secret environment values | Passed |
| `git diff --check` | Passed |
| Locked requirements exported with `uv export --locked`; checked using `pip-audit --no-deps --disable-pip` | No known vulnerabilities found after updates |

Coverage includes 508 executable statements and 110 branches across `app`,
`docker`, `migrations`, and `run`. Statement coverage is 493/508 (97.05%);
combined statement/branch coverage is 592/618 (95.79%). No first-party Python
files were omitted to reach the threshold. Shell scripts are outside Python
coverage and received syntax validation.

Added 53 test cases covering:

- Loaded revocation objects, deletion counts and retained ORM state, numeric and
  `timedelta` leeway, and exact non-session expiry boundaries.
- Field-length boundaries, required text types, email validation, normalization,
  and login identifier precedence.
- Wrong passwords, invalid UUID identities, expired tokens, concurrent session
  logout, and propagation of unrelated logout integrity errors.
- Deeply nested JSON on both registration and login.
- Configuration defaults, boolean values, required settings, origin parsing,
  and development-secret restrictions.
- Database-wait script environment handling and WSGI application initialization.

The pre-existing integration tests also continue to verify session revocation,
role changes, disabled/deleted users, rate limits, database failure responses,
uniqueness races, and migration round trips. Both migration revisions upgraded
and downgraded twice on both databases, with resulting schema checked against
model metadata. Database-wait tests mock connections and time; tests do not
require external network services. PostgreSQL validation used a disposable UTF-8
database via a private temporary Unix socket, separate from project data.

Remaining uncovered paths are principally migration offline SQL generation,
autogeneration callback compatibility branches, direct development-server
launch, a cleanup scheduling race recheck, and redundant current-user guards
that the JWT extension normally intercepts first. Actual simultaneous
multi-process request execution, container startup, and network partitions were
not exercised. No test or lint failures remain.

## 5. Remaining recommendations and limits

These are follow-up opportunities, not completed changes or newly confirmed
application defects:

1. Add CI using the existing SQLite coverage command and a disposable PostgreSQL
   service. Run the dependency audit periodically; its clean result is a dated
   snapshot, not a guarantee against undisclosed vulnerabilities.
2. Exercise Docker image build and startup in an environment with Docker daemon
   access. The local daemon socket was inaccessible to the sandbox; the local
   PostgreSQL test run supplied database integration validation instead.
3. Before scaling beyond the documented single-worker setup, configure shared
   rate-limit storage and apply migrations once per deployment, as the existing
   README already requires. No production infrastructure was altered here.
4. Add offline migration-generation and real concurrency tests if those paths
   become operational requirements. Existing conflict tests simulate races
   deterministically rather than relying on timing-sensitive threaded tests.
5. Keep the documented session-revocation retention constraint when changing
   token lifetimes: do not shorten retention while earlier tokens remain valid.

The final diff was reviewed for scope. Changes are grouped into focused commits
for cleanup, input handling, dependency security, testing, and documentation.
No deployment was performed.
