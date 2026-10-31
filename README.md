# Kowalski

An asynchronous Python security scanning engine for authorized assessments,
with a Typer/Rich CLI and an optional Flask authentication backend.
Currently supports scoped IPv4 TCP connect scans and JSON reports.

Requires Python 3.14+ and uv. Run commands from the repository root.
PostgreSQL and application secrets are required only for the backend.

## Setup

```bash
# Install locked dependencies, including development tools.
uv sync --locked
```

## Scan

```bash
# Scan explicit ports and ranges within the authorized IPv4 scope.
uv run python -m engine.scan 127.0.0.1 --allow-ip 127.0.0.1 --ports 22,5432,8000-8010

# Export a structured report.
uv run python -m engine.scan 127.0.0.1 --allow-ip 127.0.0.1 --ports 22,5432 --format json > report.json

# Show all options.
uv run python -m engine.scan --help
```

`--allow-ip` is required and repeatable. Defaults: `--timeout 1`,
`--concurrency 20`, and `--rate-limit 100` connection starts/second per scan.
Use `--no-color` to disable colored results.

Results distinguish `open` (accepted), `closed` (refused), and `unknown`
(timeout or another OS error). Open ports do not prove service identity or
vulnerabilities. DNS, IPv6, and service identification are not implemented yet.

Reports include UUID, UTC timestamps, configuration, evidence, and summary
counts. CLI scans run independently of the API and do not save to a database.
See [engine notes](engine/README.md) for the service and report interfaces.
The [scan API](docs/scans-api.md) saves reports and exposes run history.
Next: [hostname support, service identification, then React](docs/next-features.md).

## Backend setup

```bash
# Create local configuration if .env does not already exist.
cp .env.example .env

# Generate a secret to paste into SECRET_KEY in .env.
openssl rand -hex 32
```

Set `POSTGRES_PASSWORD` and matching credentials in `DATABASE_URL` in `.env`.
The default database is `kowalski`. `SECRET_KEY` must be at least 32 bytes;
leave `JWT_SECRET_KEY` empty to reuse it. Percent-encode reserved characters
in URL credentials. If changing `POSTGRES_PORT`, also update `DATABASE_URL`.

## Run backend locally

```bash
# Start PostgreSQL with persistent storage.
docker compose up -d database --wait

# Apply database migrations.
uv run flask --app run.py db upgrade

# Start the API at http://localhost:5000.
uv run flask --app run.py run

# Check API and database health from another terminal.
curl http://localhost:5000/
```

For an existing PostgreSQL server, use `createdb kowalski` instead of starting
Compose, and configure `DATABASE_URL` for that server.

## Docker

```bash
# Build and run the API and PostgreSQL; migrations run automatically.
docker compose up --build

# Follow backend logs.
docker compose logs -f backend

# Stop containers while keeping database data.
docker compose down
```

API: `http://localhost:5000`. PostgreSQL: `localhost:5432` by default.
Adding `--volumes` to `down` deletes database data.

## Migrations

Use Flask-Migrate so commands load the app configuration.

```bash
# Apply pending migrations.
uv run flask --app run.py db upgrade

# Generate a revision after changing models; review it before upgrading.
uv run flask --app run.py db migrate -m "describe change"

# Show the database's current revision.
uv run flask --app run.py db current

# Show migration history without connecting to the database.
uv run alembic -c migrations/alembic.ini history

# Check that the database schema matches the models.
uv run flask --app run.py db check
```

Current head is `72e4c01a39bf`, adding API jobs after the report tables.
The base revision is `ecf7573043bc`. Only if your database already applied
**both old revisions**, ending at `a1c7d93e840f`, update its revision marker:

```bash
uv run flask --app run.py db stamp --purge ecf7573043bc
uv run flask --app run.py db upgrade
uv run flask --app run.py db check
```

Stamping changes only the revision marker, not the schema. Fresh databases use
`db upgrade`; databases with only the old base still need the session column
and index.

## Quality and maintenance

GitHub Actions runs tests with coverage on pushes and pull requests.

```bash
# Check formatting and lint.
uv run ruff format --check .
uv run ruff check .

# Run tests with isolated SQLite and loopback sockets; enforce 85% coverage.
uv run pytest --cov --cov-report=term-missing

# Test against PostgreSQL: use a disposable database; tables are dropped.
uv run pytest --database-url 'postgresql://<user>:<password>@localhost:<port>/<test-db>'

# Remove expired token revocation records.
uv run flask --app run.py cleanup-token-blocklist
```

## API

| Method | Route | Description |
| --- | --- | --- |
| GET | `/` | Database health |
| POST | `/auth/register` | Create a user and return tokens |
| POST | `/auth/login` | Log in with email or username |
| POST | `/auth/refresh` | Get an access token using a refresh token |
| POST | `/auth/logout` | Revoke the access/refresh session |
| GET | `/auth/me` | Current user |
| GET | `/auth/admin-only` | Admin access check |

Protected routes use `Authorization: Bearer <token>`. New users have the
`regular` role; no admin is seeded.

| Method | Route | Description |
| --- | --- | --- |
| POST | `/scans` | Queue a TCP scan (`202`) |
| GET | `/scans` | List owned scan requests |
| GET | `/scans/<id>` | Status and completed report |
| GET | `/scans/history?target=<ip>` | Observations and changes across runs |

Run `uv run flask --app run.py scan-worker` alongside the API; Compose starts
the worker automatically. Targets are supplied in requests, with no environment
allowlist. See [API usage](docs/scans-api.md).
