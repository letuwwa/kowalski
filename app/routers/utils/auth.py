import re
import uuid
from datetime import UTC, datetime, timedelta

from flask import current_app, request
from flask_jwt_extended import create_access_token, create_refresh_token

from app.models import User

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def create_token_pair(user: User) -> dict[str, str]:
    identity = str(user.id)
    session_id = str(uuid.uuid4())
    refresh_expires = current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]
    if type(refresh_expires) is int:
        refresh_expires = timedelta(seconds=refresh_expires)
    session_expires_at = int((datetime.now(UTC) + refresh_expires).timestamp())
    additional_claims = {
        "role": user.role.value,
        "sid": session_id,
        "sexp": session_expires_at,
    }
    return {
        "access_token": create_access_token(
            identity=identity,
            additional_claims=additional_claims,
        ),
        "refresh_token": create_refresh_token(
            identity=identity,
            additional_claims={**additional_claims, "exp": session_expires_at},
        ),
    }


def json_body() -> dict:
    try:
        data = request.get_json(silent=True)
    except RecursionError:
        # silent=True handles malformed JSON, but not the decoder's depth limit.
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def validate_register_payload(data: dict) -> dict[str, str]:
    errors = {}

    email = string_value(data, "email").strip().lower()
    username = string_value(data, "username").strip().lower()
    password = string_value(data, "password")
    first_name = string_value(data, "first_name").strip()
    last_name = string_value(data, "last_name").strip()

    if not EMAIL_PATTERN.match(email) or len(email) > 255:
        errors["email"] = "A valid email is required"

    if not 3 <= len(username) <= 100 or not USERNAME_PATTERN.match(username):
        errors["username"] = (
            "Username must be 3-100 characters and contain only lowercase letters, "
            "numbers, underscores, and hyphens"
        )

    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        errors["password"] = "Password must be 12-128 characters"

    if not 1 <= len(first_name) <= 30:
        errors["first_name"] = "First name must be 1-30 characters"

    if not 1 <= len(last_name) <= 30:
        errors["last_name"] = "Last name must be 1-30 characters"

    return errors


def string_value(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or "\x00" in value:
        return ""
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return ""
    return value


def login_identifier(data: dict) -> str:
    for key in ("identifier", "email", "username"):
        value = string_value(data, key).strip().lower()
        if value:
            return value
    return ""
