import os
from datetime import timedelta
from pathlib import Path
from typing import ClassVar

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"{name} environment variable is required")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value")


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return value


def _env_csv(name: str, default: str = "*") -> str | list[str]:
    value = os.getenv(name, default)
    if value == "*":
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


def _jwt_secret_key() -> str:
    value = os.getenv("JWT_SECRET_KEY")
    if value and len(value.encode()) >= 32:
        return value

    if value:
        raise RuntimeError("JWT_SECRET_KEY must be at least 32 bytes")

    secret_key = os.getenv("SECRET_KEY")
    if secret_key and len(secret_key.encode()) >= 32:
        return secret_key

    if _env_bool("FLASK_DEBUG"):
        return "dev-jwt-secret-key-change-me-for-local-use-only"

    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is required unless SECRET_KEY is at "
        "least 32 bytes"
    )


def _secret_key() -> str:
    value = os.getenv("SECRET_KEY")
    if value and len(value.encode()) >= 32:
        return value

    if value and not _env_bool("FLASK_DEBUG"):
        raise RuntimeError("SECRET_KEY must be at least 32 bytes")

    if _env_bool("FLASK_DEBUG"):
        return "dev-secret-key-change-me-for-local-use-only"

    raise RuntimeError("SECRET_KEY environment variable is required")


class Config:
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    RATELIMIT_HEADERS_ENABLED = True

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict[str, int | bool]] = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    def __init__(self):
        self.DEBUG = _env_bool("FLASK_DEBUG")
        self.SECRET_KEY = _secret_key()
        self.JWT_SECRET_KEY = _jwt_secret_key()
        self.CORS_ORIGINS = _env_csv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        )
        self.RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
        self.TOKEN_BLOCKLIST_CLEANUP_INTERVAL = _env_int(
            "TOKEN_BLOCKLIST_CLEANUP_INTERVAL", 3600, minimum=1
        )
        self.MAX_CONTENT_LENGTH = _env_int("MAX_CONTENT_LENGTH", 1_048_576, minimum=1)
        self.SQLALCHEMY_DATABASE_URI = _required_env("DATABASE_URL")
