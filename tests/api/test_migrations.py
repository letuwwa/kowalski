import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    Uuid,
    column,
    inspect,
    table,
    text,
)

from api.extensions import db
from api.models import ScanJob, ScanRun, TCPPortResult, User
from api.services.reports import report_from_run


def test_migrations_round_trip_and_match_models(app):
    db.drop_all()
    with db.engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    runner = app.test_cli_runner()
    try:
        for _ in range(2):
            result = runner.invoke(args=["db", "upgrade"])
            assert result.exit_code == 0, result.output
            result = runner.invoke(args=["db", "check"])
            assert result.exit_code == 0, result.output
            inspector = inspect(db.engine)
            assert {
                item["name"]
                for item in inspector.get_check_constraints("tcp_port_results")
            } == {
                "ck_tcp_port_results_port",
                "ck_tcp_port_results_state",
            }
            assert inspector.get_unique_constraints("tcp_port_results")[0][
                "column_names"
            ] == ["scan_id", "ip_address", "port"]
            result = runner.invoke(args=["db", "downgrade", "base"])
            assert result.exit_code == 0, result.output
            inspector = inspect(db.engine)
            assert set(inspector.get_table_names()) == {"alembic_version"}
            if db.engine.dialect.name == "postgresql":
                assert not any(
                    item["name"] == "user_role" for item in inspector.get_enums()
                )
    finally:
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


def test_report_migration_preserves_existing_users(app):
    db.drop_all()
    runner = app.test_cli_runner()
    result = runner.invoke(args=["db", "upgrade", "ecf7573043bc"])
    assert result.exit_code == 0, result.output
    now = datetime.now(UTC)
    user = User(
        email="existing@example.test",
        username="existing",
        first_name="Existing",
        last_name="User",
        password_hash="unused",
        created_at=now,
        updated_at=now,
    )
    db.session.add(user)
    db.session.commit()
    user_id = user.id
    try:
        result = runner.invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, result.output
        scan = ScanRun(
            id=uuid.uuid4(),
            user_id=user_id,
            target="127.0.0.1",
            started_at=now,
            completed_at=now,
            configuration={"ports": [22]},
            schema_version=1,
            tcp_port_results=[
                TCPPortResult(
                    ip_address="127.0.0.1", port=22, state="open", evidence="Accepted"
                )
            ],
        )
        db.session.add(scan)
        db.session.commit()
        assert db.session.get(ScanRun, scan.id).tcp_port_results[0].port == 22
        db.session.remove()
        result = runner.invoke(args=["db", "downgrade", "ecf7573043bc"])
        assert result.exit_code == 0, result.output
        assert "scan_runs" not in inspect(db.engine).get_table_names()
        assert db.session.get(User, user_id).username == "existing"
        db.session.remove()
        result = runner.invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, result.output
        result = runner.invoke(args=["db", "check"])
        assert result.exit_code == 0, result.output
    finally:
        db.session.remove()
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


def test_hostname_migration_backfills_old_evidence_and_guards_downgrade(app):
    db.drop_all()
    runner = app.test_cli_runner()
    result = runner.invoke(args=["db", "upgrade", "72e4c01a39bf"])
    assert result.exit_code == 0, result.output
    now = datetime.now(UTC)
    owner = User(
        email="legacy@example.test",
        username="legacy",
        first_name="Old",
        last_name="Owner",
        password_hash="unused",
        created_at=now,
        updated_at=now,
    )
    db.session.add(owner)
    db.session.flush()
    owner_id = owner.id
    configuration = {
        "ports": [443],
        "allowed_targets": ["127.0.0.1"],
        "timeout": 1,
        "concurrency": 20,
        "rate_limit": 100,
    }
    legacy_run = ScanRun(
        id=uuid.uuid4(),
        user_id=owner_id,
        target="127.0.0.1",
        started_at=now,
        completed_at=now,
        configuration=configuration,
        schema_version=1,
    )
    # Insert only columns available at the old migration revision.
    run_id = legacy_run.id
    db.session.execute(
        ScanRun.__table__.insert().values(
            id=run_id,
            user_id=owner_id,
            target=legacy_run.target,
            started_at=now,
            completed_at=now,
            configuration=configuration,
            schema_version=1,
        )
    )
    # Describe the old child table, which has no destination-address column yet.
    old_results = table(
        "tcp_port_results",
        column("id", Uuid),
        column("scan_id", Uuid),
        column("port", Integer),
        column("state", String),
        column("evidence", Text),
        column("created_at", DateTime(timezone=True)),
        column("updated_at", DateTime(timezone=True)),
    )
    db.session.execute(
        old_results.insert().values(
            id=uuid.uuid4(),
            scan_id=run_id,
            port=443,
            state="open",
            evidence="Legacy accepted",
            created_at=now,
            updated_at=now,
        )
    )
    db.session.commit()
    db.session.remove()
    try:
        result = runner.invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, result.output
        stored = db.session.get(ScanRun, run_id)
        assert stored.tcp_port_results[0].ip_address == "127.0.0.1"
        assert stored.tcp_port_results[0].evidence == "Legacy accepted"
        report = report_from_run(stored)
        assert report.schema_version == 1
        assert report.resolved_ips == ("127.0.0.1",)
        host = ScanRun(
            id=uuid.uuid4(),
            user_id=owner_id,
            target="scan.example.test",
            started_at=now,
            completed_at=now,
            configuration=configuration,
            schema_version=2,
            tcp_port_results=[
                TCPPortResult(
                    ip_address="127.0.0.2", port=443, state="open", evidence="Accepted"
                )
            ],
        )
        queued = ScanJob(
            user_id=owner_id, target="queued.example.test", configuration=configuration
        )
        db.session.add_all([host, queued])
        db.session.commit()
        host_id, job_id = host.id, queued.id
        db.session.remove()
        result = runner.invoke(args=["db", "downgrade", "72e4c01a39bf"])
        assert result.exit_code != 0
        assert "Cannot downgrade" in result.output, result.output
        # Earlier downgrade steps may have completed before the hostname guard.
        result = runner.invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, result.output
        assert (
            db.session.get(ScanRun, host_id).tcp_port_results[0].ip_address
            == "127.0.0.2"
        )
        db.session.delete(db.session.get(ScanRun, host_id))
        db.session.commit()
        db.session.remove()
        result = runner.invoke(args=["db", "downgrade", "72e4c01a39bf"])
        assert result.exit_code != 0  # A queued hostname must be preserved too.
        result = runner.invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, result.output
        db.session.delete(db.session.get(ScanJob, job_id))
        db.session.commit()
        db.session.remove()
        result = runner.invoke(args=["db", "downgrade", "72e4c01a39bf"])
        assert result.exit_code == 0, result.output
        result = runner.invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, result.output
        result = runner.invoke(args=["db", "check"])
        assert result.exit_code == 0, result.output
        assert (
            db.session.get(ScanRun, run_id).tcp_port_results[0].evidence
            == "Legacy accepted"
        )
    finally:
        db.session.remove()
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


def test_service_migration_preserves_evidence_and_guards_downgrade(app):
    db.drop_all()
    runner = app.test_cli_runner()
    try:
        result = runner.invoke(args=["db", "upgrade", "35ae702d91c4"])
        assert result.exit_code == 0, result.output
        assert "services" not in {
            col["name"] for col in inspect(db.engine).get_columns("scan_runs")
        }
        result = runner.invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, result.output
        now = datetime.now(UTC)
        owner = User(
            email="migration@example.test",
            username="migration",
            first_name="Test",
            last_name="User",
            password_hash="unused",
            created_at=now,
            updated_at=now,
        )
        db.session.add(owner)
        db.session.flush()
        now = datetime.now(UTC)
        run = ScanRun(
            id=uuid.uuid4(),
            user_id=owner.id,
            target="127.0.0.1",
            started_at=now,
            completed_at=now,
            configuration={},
            schema_version=3,
            created_at=now,
            updated_at=now,
            services=[{"status": "timeout", "evidence_base64": ""}],
        )
        db.session.add(run)
        db.session.commit()
        identifier = run.id
        db.session.remove()
        result = runner.invoke(args=["db", "downgrade", "35ae702d91c4"])
        assert result.exit_code != 0
        assert "Cannot downgrade" in result.output
        run = db.session.get(ScanRun, identifier)
        assert run.services == [{"status": "timeout", "evidence_base64": ""}]
        run.services = []
        db.session.commit()
        db.session.remove()
        result = runner.invoke(args=["db", "downgrade", "35ae702d91c4"])
        assert result.exit_code == 0, result.output
        result = runner.invoke(args=["db", "upgrade"])
        assert result.exit_code == 0, result.output
        assert db.session.get(ScanRun, identifier).services is None
    finally:
        db.session.remove()
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
