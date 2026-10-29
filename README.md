# Flask Template

Flask API starter with PostgreSQL, SQLAlchemy, Alembic migrations, JWT auth,
password hashing, refresh token support, logout token revocation, CORS, Docker,
and role-based admin protection.

## Stack

- Python 3.14.7
- Flask 3
- PostgreSQL 18.6
- SQLAlchemy and Flask-Migrate
- Flask-JWT-Extended
- Flask-Limiter
- Gunicorn
- uv
- Ruff

## Requirements

- Python 3.14+ (the container currently uses 3.14.7)
- uv
- PostgreSQL for local development, or Docker Compose for the full stack

## Local Setup

Install the locked dependencies:

```bash
uv sync --locked
```

Create a `.env` file:

```env
DATABASE_URL=postgresql://postgres:<database-password>@localhost:5432/flask_template
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<database-password>
POSTGRES_PORT=5432
SECRET_KEY=<long-random-secret>
JWT_SECRET_KEY=<long-random-secret>
FLASK_DEBUG=false
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
RATELIMIT_STORAGE_URI=memory://
MAX_CONTENT_LENGTH=1048576
```

You can start from the checked-in example with `cp .env.example .env`.
Set `POSTGRES_PASSWORD`, update the password in `DATABASE_URL`, and generate a
`SECRET_KEY` before starting. The example deliberately leaves secrets empty.
`JWT_SECRET_KEY` can be left empty to use `SECRET_KEY`.

Generate suitable local secrets:

```bash
openssl rand -hex 32
```

`DATABASE_URL` and a `SECRET_KEY` of at least 32 bytes are required outside
debug mode. Invalid boolean and integer configuration values stop startup with
a clear error instead of silently selecting a potentially unsafe default.
`JWT_SECRET_KEY`, when set, must also be at least 32 bytes; otherwise the app
uses `SECRET_KEY` for JWT signing. In debug mode only, the app can fall back to
development secrets.

Configuration is read and validated for each `create_app()` call. Environment
variables take precedence over `.env`. Keep `FLASK_DEBUG=false` outside local
development; debug mode permits predictable development signing keys.

When embedding credentials in `DATABASE_URL`, percent-encode reserved URL
characters in the username and password. Compose passes credentials separately
and does not require URL encoding of `POSTGRES_PASSWORD`.

## Database

Start the persistent PostgreSQL database on localhost:

```bash
docker compose up -d database --wait
```

The default host port is `127.0.0.1:5432`. If that port is occupied, set
`POSTGRES_PORT` in `.env` and use the same port in `DATABASE_URL`, for example:

```env
POSTGRES_PORT=5433
DATABASE_URL=postgresql://postgres:<database-password>@localhost:5433/flask_template
```

Database files are stored in the `postgres_data` named volume and survive
container recreation. PostgreSQL 18 uses `/var/lib/postgresql` as its persistent
volume root.

Alternatively, when using a system PostgreSQL server, create the database with
`createdb flask_template`.

Run migrations:

```bash
uv run flask --app run.py db upgrade
```

Create a migration after model changes:

```bash
uv run flask --app run.py db migrate -m "describe change"
```

## Run Locally

Start the development server:

```bash
uv run flask --app run.py run
```

The API runs at `http://localhost:5000`.

Check the health endpoint:

```bash
curl http://localhost:5000/
```

## Docker

Build and run the API with PostgreSQL:

```bash
docker compose up --build
```

The backend waits for PostgreSQL to become healthy, runs migrations, removes
expired revocation records, then starts Gunicorn as an unprivileged user on
`http://localhost:5000`.

The container user has a writable home at `/home/app`, which Gunicorn uses for
its local control socket; the application code remains owned by root.

Docker Compose starts a `backend` service and a `database` service. The backend
connects to PostgreSQL through the internal Compose hostname:

```env
DATABASE_URL=postgresql://database:5432/flask_template
PGUSER=<database-user>
PGPASSWORD=<database-password>
```

Compose supplies `PGUSER` and `PGPASSWORD` from `POSTGRES_USER` and
`POSTGRES_PASSWORD`. These are standard [libpq connection environment
variables](https://www.postgresql.org/docs/current/libpq-envars.html). This
avoids parsing passwords as URL or shell syntax. For production deployments,
consider a mounted password file or secret manager instead of environment
secrets, and terminate HTTPS at a trusted reverse proxy.

Startup retries database connections for `DATABASE_WAIT_TIMEOUT` seconds
(default 60), using a monotonic clock and connection timeouts of 2–5 seconds.
This is a retry budget, not a strict wall-clock deadline: DNS resolution and
libpq connection attempts may extend it. `TOKEN_BLOCKLIST_CLEANUP_INTERVAL`
controls cleanup frequency in seconds (default 3600). Both must be positive
integers. When scaling beyond one container, run migrations once as a separate
deployment step before starting application replicas.

The API and PostgreSQL ports bind only to `127.0.0.1`. Containers communicate
over the private Compose network while host-side tools can connect through the
configured `POSTGRES_PORT`.

Stop and remove the containers:

```bash
docker compose down
```

`docker compose down` preserves database data. Add `--volumes` only when you
intentionally want to delete the local database.

## Authentication

Register a user:

```bash
curl -X POST http://localhost:5000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "exampleuser",
    "first_name": "Example",
    "last_name": "User",
    "password": "password123456"
  }'
```

Login with an email, username, or `identifier`:

```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "user@example.com",
    "password": "password123456"
  }'
```

Call an authenticated endpoint:

```bash
curl http://localhost:5000/auth/me \
  -H "Authorization: Bearer <access-token>"
```

Refresh an access token with a refresh token:

```bash
curl -X POST http://localhost:5000/auth/refresh \
  -H "Authorization: Bearer <refresh-token>"
```

Logout with either token. The complete access/refresh session is revoked:

```bash
curl -X POST http://localhost:5000/auth/logout \
  -H "Authorization: Bearer <access-or-refresh-token>"
```

## API Routes

```text
GET  /                 Health check
POST /auth/register    Create a regular user and return token pair
POST /auth/login       Return the user and token pair
POST /auth/refresh     Return a new access token from a refresh token
POST /auth/logout      Revoke the complete access/refresh token session
GET  /auth/me          Return the current user
GET  /auth/admin-only  Require an admin user
```

Newly registered users use the `regular` role. The base migration creates the
users and token blocklist tables; it does not seed an admin user.

Registration is limited to 5 requests per hour per client address, and login is
limited to 10 requests per minute. The in-memory limiter is suitable for the
default single-worker setup. Configure a shared Flask-Limiter storage URI, such
as Redis, before running multiple workers or application instances.

Request bodies are limited to 1 MiB by default (`MAX_CONTENT_LENGTH`), auth
responses disable caching, and API responses include MIME-sniffing protection.

Expired revocation records are cleaned hourly during authenticated traffic and
at container startup. Session revocations are retained for an additional access
token lifetime plus clock-skew and rounding margins: a refresh near expiration
can issue an access token that remains valid afterward. Cleanup also protects
records written by earlier versions. If changing token lifetimes in code, do
not shorten the retention window until previously issued tokens have expired.
Tokens issued before session IDs were introduced can still be logged out, but
only that individual token can be revoked. Existing records that have already
been deleted cannot be recovered by this fix.

Revocation records can also be cleaned manually:

```bash
uv run flask --app run.py cleanup-token-blocklist
```

## Registration Validation

```text
email       Valid email, max 255 characters
username    3-100 characters; lowercase letters, numbers, underscores, hyphens
password    12-128 characters
first_name  1-30 characters
last_name   1-30 characters
```

Text must be valid UTF-8 and contain no NUL characters. Login rejects passwords
over 128 characters before hashing. Email and username comparisons normalize
case and surrounding whitespace. Authorization checks the current database
role and active status, not the role claim from an old token.

## Quality

Run Ruff:

```bash
uv run ruff format --check .
uv run ruff check .
```

Run the automated tests:

```bash
uv run pytest
```

Measure statement and branch coverage, including the app, startup helper,
migrations, and WSGI entrypoint:

```bash
uv run pytest --cov --cov-report=term-missing
```

Coverage runs enforce an 85% minimum. Tests include regression coverage for
loaded SQLite revocation records, JWT clock-skew settings, and deeply nested
JSON request bodies. See [AUDIT_REPORT.md](AUDIT_REPORT.md) for the latest
stabilization findings and validation results.

Tests use an isolated in-memory SQLite database and in-memory rate limits by
default. To exercise PostgreSQL constraints, enums, and migration round trips:

```bash
uv run pytest --database-url 'postgresql://<user>:<password>@localhost:<port>/<test-db>'
```

**Use a disposable database only.** This suite creates and drops application
tables and runs migration downgrades. Never point it at development or
production data. Migration coverage upgrades and downgrades twice and checks
the resulting schema against model metadata. No separate type checker is
configured.

Audit locked dependencies for published vulnerabilities:

```bash
uv export --locked --no-hashes --no-emit-project --format requirements-txt \
  --output-file /tmp/flask-template-audit-requirements.txt
uvx pip-audit -r /tmp/flask-template-audit-requirements.txt --no-deps --disable-pip
```

This audits the pinned runtime and development dependencies without installing
`pip-audit` into the project. An audit on 2026-10-29 reported no known
vulnerabilities; this is not a guarantee against undisclosed vulnerabilities.

## Project Layout

```text
run.py                         Flask entrypoint
app/__init__.py                App factory
app/config.py                  Environment-based config
app/extensions.py              Flask extension registration
app/routers/index.py           Health endpoint
app/routers/auth.py            Auth routes
app/models/base_model.py       Shared model fields
app/models/user.py             User model and roles
app/models/token_blocklist.py  Revoked JWT storage
migrations/versions/           Alembic migrations
docker/entrypoint.sh           Container DB wait and migration startup
docker/wait_for_db.py          Bounded PostgreSQL connection retries
docker-compose.yml             Backend and PostgreSQL services
Dockerfile                     Backend image
```
