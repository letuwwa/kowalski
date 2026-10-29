from sqlalchemy import inspect, text

from app.extensions import db


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
