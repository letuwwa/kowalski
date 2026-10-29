import pytest

from app import create_app
from app.config import _env_bool, _env_int, _jwt_secret_key, _secret_key


def test_invalid_boolean_configuration_fails_fast(monkeypatch):
    monkeypatch.setenv("INVALID_BOOLEAN", "sometimes")

    with pytest.raises(RuntimeError, match="must be a boolean"):
        _env_bool("INVALID_BOOLEAN")


def test_invalid_integer_configuration_fails_fast(monkeypatch):
    monkeypatch.setenv("INVALID_INTEGER", "never")

    with pytest.raises(RuntimeError, match="must be an integer"):
        _env_int("INVALID_INTEGER", 1)


def test_short_production_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "short")
    monkeypatch.setenv("FLASK_DEBUG", "false")

    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        _secret_key()


def test_short_jwt_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "short")

    with pytest.raises(RuntimeError, match="at least 32 bytes"):
        _jwt_secret_key()


def test_factory_reads_current_environment(app, monkeypatch):
    monkeypatch.setenv("MAX_CONTENT_LENGTH", "2048")
    monkeypatch.setenv("SECRET_KEY", "different-secret-with-at-least-32-bytes")
    another = create_app()
    assert another.config["MAX_CONTENT_LENGTH"] == 2048
    assert another.config["SECRET_KEY"] != app.config["SECRET_KEY"]
    assert app.config["MAX_CONTENT_LENGTH"] == 1_048_576


def test_factory_revalidates_environment(app, monkeypatch):
    monkeypatch.setenv("MAX_CONTENT_LENGTH", "0")
    with pytest.raises(RuntimeError, match="at least 1"):
        create_app()


def test_jwt_secret_falls_back_to_secret_key(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    assert _jwt_secret_key() == _secret_key()


def test_production_requires_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "false")
    with pytest.raises(RuntimeError, match="required"):
        _secret_key()


@pytest.mark.parametrize("value", ["1", "TRUE", "yes", "on"])
def test_truthy_configuration(monkeypatch, value):
    monkeypatch.setenv("BOOLEAN", value)
    assert _env_bool("BOOLEAN") is True


def test_configuration_defaults_and_required_values(monkeypatch):
    from app.config import _env_csv, _required_env

    monkeypatch.delenv("ABSENT_SETTING", raising=False)
    assert _env_bool("ABSENT_SETTING", True) is True
    assert _env_int("ABSENT_SETTING", 42) == 42
    assert _env_csv("ABSENT_SETTING") == "*"
    with pytest.raises(RuntimeError, match="required"):
        _required_env("ABSENT_SETTING")
    monkeypatch.setenv("ABSENT_SETTING", "")
    with pytest.raises(RuntimeError, match="required"):
        _required_env("ABSENT_SETTING")
    monkeypatch.setenv("ABSENT_SETTING", " https://one.example, ,https://two.example ")
    assert _env_csv("ABSENT_SETTING") == ["https://one.example", "https://two.example"]


def test_development_secret_fallbacks_require_debug(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_DEBUG", "true")
    assert len(_secret_key().encode()) >= 32
    assert len(_jwt_secret_key().encode()) >= 32
    monkeypatch.setenv("FLASK_DEBUG", "false")
    with pytest.raises(RuntimeError, match="required"):
        _jwt_secret_key()
