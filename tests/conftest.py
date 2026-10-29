import pytest

from app import create_app
from app.extensions import db, limiter


def pytest_addoption(parser):
    parser.addoption(
        "--database-url",
        default="sqlite://",
        help="Disposable test database URL. Tests create and DROP application tables.",
    )


@pytest.fixture
def app(monkeypatch, request):
    monkeypatch.setenv("DATABASE_URL", request.config.getoption("--database-url"))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-with-at-least-32-bytes")
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")
    monkeypatch.setenv("MAX_CONTENT_LENGTH", "1048576")
    monkeypatch.setenv("TOKEN_BLOCKLIST_CLEANUP_INTERVAL", "3600")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")
    application = create_app()
    application.config.update(
        TESTING=True,
        RATELIMIT_ENABLED=True,
        TOKEN_BLOCKLIST_CLEANUP_INTERVAL=3600,
    )

    with application.app_context():
        db.create_all()
        limiter.reset()
        try:
            yield application
        finally:
            limiter.reset()
            db.session.remove()
            db.drop_all()
            db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()
