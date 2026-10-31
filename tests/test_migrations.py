import uuid
from datetime import UTC, datetime

from sqlalchemy import inspect, text

from app.extensions import db
from app.models import ScanRun, TCPPortResult, User


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
            ] == ["scan_id", "port"]
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
                TCPPortResult(port=22, state="open", evidence="Accepted")
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
