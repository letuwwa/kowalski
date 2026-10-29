from datetime import UTC, datetime, timedelta

import pytest
from flask_jwt_extended import create_refresh_token, decode_token
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import cleanup_expired_tokens, db
from app.models import TokenBlocklist, User, UserRole

REGISTER_PAYLOAD = {
    "email": "user@example.com",
    "username": "exampleuser",
    "first_name": "Example",
    "last_name": "User",
    "password": "password123456",
}


def register(client):
    response = client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    return response.get_json()["tokens"]


def test_logout_revokes_access_and_refresh_tokens(client):
    tokens = register(client)

    response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    assert (
        client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        ).status_code
        == 401
    )


def test_refresh_preserves_session_revocation(client):
    tokens = register(client)
    refreshed = client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert refreshed.status_code == 200
    access_token = refreshed.get_json()["access_token"]

    assert (
        client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        ).status_code
        == 401
    )


def test_cleanup_deletes_only_expired_revocations(app):
    now = datetime.now(UTC)
    db.session.add_all(
        [
            TokenBlocklist(
                jti="expired",
                token_type="access",
                user_id="user",
                expires_at=now - timedelta(minutes=1),
            ),
            TokenBlocklist(
                jti="active",
                token_type="access",
                user_id="user",
                expires_at=now + timedelta(minutes=1),
            ),
        ]
    )
    db.session.commit()

    assert cleanup_expired_tokens() == 1
    remaining = db.session.scalars(select(TokenBlocklist)).one()
    assert remaining.jti == "active"


def test_login_is_rate_limited(client):
    responses = [
        client.post(
            "/auth/login",
            json={"identifier": "missing@example.com", "password": "wrong"},
        )
        for _ in range(11)
    ]

    assert all(response.status_code == 401 for response in responses[:10])
    assert responses[10].status_code == 429
    assert responses[10].get_json() == {"message": "Rate limit exceeded"}


def test_authentication_responses_disable_caching(client):
    response = client.post("/auth/login", json={})

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_oversized_request_returns_json_error(client):
    response = client.post(
        "/auth/register",
        data=b"x" * 1_048_577,
        content_type="application/json",
    )

    assert response.status_code == 413
    assert response.get_json() == {"message": "Request body is too large"}


def test_registration_conflicts_with_two_different_users(client):
    register(client)
    second = {**REGISTER_PAYLOAD, "email": "second@example.com", "username": "second"}
    assert client.post("/auth/register", json=second).status_code == 201

    response = client.post(
        "/auth/register", json={**REGISTER_PAYLOAD, "username": "second"}
    )
    assert response.status_code == 409


def test_logout_retains_revocation_for_access_tokens_after_refresh_expiry(
    client, monkeypatch
):
    tokens = register(client)
    identity = decode_token(tokens["access_token"])["sub"]
    session_end = int((datetime.now(UTC) + timedelta(seconds=30)).timestamp())
    refresh_token = create_refresh_token(
        identity=identity,
        expires_delta=timedelta(seconds=30),
        additional_claims={"sid": "expiring-session", "sexp": session_end},
    )
    response = client.post(
        "/auth/refresh", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    access_token = response.get_json()["access_token"]
    assert (
        client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {refresh_token}"}
        ).status_code
        == 200
    )

    class AfterRefreshExpiry(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromtimestamp(session_end + 1, tz=tz)

    monkeypatch.setattr("app.extensions.datetime", AfterRefreshExpiry)
    monkeypatch.setattr("jwt.api_jwt.datetime", AfterRefreshExpiry)
    assert cleanup_expired_tokens() == 0
    assert (
        client.get(
            "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        ).status_code
        == 401
    )


def test_legacy_refresh_token_can_be_refreshed_and_logged_out(client):
    tokens = register(client)
    legacy = create_refresh_token(identity=decode_token(tokens["access_token"])["sub"])
    response = client.post(
        "/auth/refresh", headers={"Authorization": f"Bearer {legacy}"}
    )
    access = response.get_json()["access_token"]
    response = client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {access}"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize("field", ["email", "first_name", "last_name", "password"])
@pytest.mark.parametrize("invalid", ["\u0000", "\ud800"])
def test_registration_rejects_unstorable_text(client, field, invalid):
    response = client.post(
        "/auth/register",
        json={**REGISTER_PAYLOAD, field: REGISTER_PAYLOAD[field] + invalid},
    )
    assert response.status_code == 400
    assert field in response.get_json()["errors"]


def test_login_rejects_oversized_password_without_hashing(client, monkeypatch):
    register(client)

    def unexpected_hash(*args):
        pytest.fail("Oversized passwords must be rejected before hashing")

    monkeypatch.setattr(User, "check_password", unexpected_hash)
    response = client.post(
        "/auth/login",
        json={"username": REGISTER_PAYLOAD["username"], "password": "x" * 129},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("key", ["identifier", "email", "username"])
def test_login_accepts_normalized_identifiers(client, key):
    register(client)
    identifier = REGISTER_PAYLOAD["username" if key == "username" else "email"]
    response = client.post(
        "/auth/login",
        json={key: f" {identifier.upper()} ", "password": REGISTER_PAYLOAD["password"]},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]
    assert set(body["tokens"]) == {"access_token", "refresh_token"}


@pytest.mark.parametrize("body", [None, [], "text", 42, {"email": []}])
def test_malformed_registration_and_login_return_client_errors(client, body):
    assert client.post("/auth/register", json=body).status_code == 400
    assert client.post("/auth/login", json=body).status_code == 401


def test_registration_ignores_privileged_fields(client):
    response = client.post(
        "/auth/register", json={**REGISTER_PAYLOAD, "role": "admin", "is_active": False}
    )
    assert response.status_code == 201
    user = response.get_json()["user"]
    assert user["role"] == "regular"
    assert user["is_active"] is True


def test_admin_authorization_uses_current_database_role(client):
    tokens = register(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/auth/admin-only", headers=headers).status_code == 403
    user = db.session.scalars(select(User)).one()
    user.role = UserRole.ADMIN
    db.session.commit()
    assert client.get("/auth/admin-only", headers=headers).status_code == 200
    user.role = UserRole.REGULAR
    db.session.commit()
    assert client.get("/auth/admin-only", headers=headers).status_code == 403


def test_disabled_user_cannot_login_refresh_or_access_protected_routes(client):
    tokens = register(client)
    user = db.session.scalars(select(User)).one()
    user.is_active = False
    db.session.commit()
    assert client.post("/auth/login", json=REGISTER_PAYLOAD).status_code == 403
    for path in ["/auth/me", "/auth/admin-only"]:
        assert (
            client.get(
                path, headers={"Authorization": f"Bearer {tokens['access_token']}"}
            ).status_code
            == 403
        )
    assert (
        client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        ).status_code
        == 200
    )


def test_logout_does_not_revoke_other_login_sessions(client):
    first = register(client)
    second = client.post("/auth/login", json=REGISTER_PAYLOAD).get_json()["tokens"]
    assert (
        client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {first['access_token']}"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"}
        ).status_code
        == 200
    )


def test_refresh_token_is_not_accepted_as_access_token(client):
    tokens = register(client)
    assert (
        client.get(
            "/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        ).status_code
        == 422
    )


def test_deleted_user_token_is_rejected(client):
    tokens = register(client)
    db.session.delete(db.session.scalars(select(User)).one())
    db.session.commit()
    assert (
        client.get(
            "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        ).status_code
        == 401
    )


def test_session_cleanup_includes_access_lifetime_and_clock_leeway(app):
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 60
    app.config["JWT_DECODE_LEEWAY"] = 30
    now = datetime.now(UTC)
    for jti, sid, age in [
        ("old-session", "old", 180),
        ("live-session", "live", 90),
        ("leeway-token", None, 10),
        ("expired-token", None, 40),
    ]:
        db.session.add(
            TokenBlocklist(
                jti=jti,
                session_id=sid,
                token_type="access",
                user_id="user",
                expires_at=now - timedelta(seconds=age),
            )
        )
    db.session.commit()
    assert cleanup_expired_tokens() == 2
    assert set(db.session.scalars(select(TokenBlocklist.jti))) == {
        "live-session",
        "leeway-token",
    }


def test_integer_refresh_lifetime_preserves_session_expiry(app, client):
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = 60
    tokens = register(client)
    access = decode_token(tokens["access_token"])
    refresh = decode_token(tokens["refresh_token"])
    assert access["sexp"] == refresh["sexp"] == refresh["exp"]


def test_registration_handles_uniqueness_race_with_two_conflicts(client, monkeypatch):
    register(client)
    assert (
        client.post(
            "/auth/register",
            json={
                **REGISTER_PAYLOAD,
                "email": "second@example.com",
                "username": "second",
            },
        ).status_code
        == 201
    )
    execute = db.session.execute
    first_query = True

    def simulate_stale_precheck(statement, *args, **kwargs):
        nonlocal first_query
        if first_query:
            first_query = False
            return execute(select(User.id).where(False))
        return execute(statement, *args, **kwargs)

    monkeypatch.setattr(db.session, "execute", simulate_stale_precheck)
    response = client.post(
        "/auth/register", json={**REGISTER_PAYLOAD, "username": "second"}
    )
    assert response.status_code == 409
    assert len(db.session.scalars(select(User)).all()) == 2


def test_registration_does_not_hide_unrelated_integrity_errors(client, monkeypatch):
    def fail_commit():
        raise IntegrityError("INSERT", {}, Exception("unrelated constraint"))

    monkeypatch.setattr(db.session, "commit", fail_commit)
    with pytest.raises(IntegrityError):
        client.post("/auth/register", json=REGISTER_PAYLOAD)


def test_registration_is_rate_limited(client):
    responses = [client.post("/auth/register", json={}) for _ in range(6)]
    assert [response.status_code for response in responses] == [400] * 5 + [429]


@pytest.mark.parametrize("path", ["/auth/me", "/auth/admin-only"])
def test_protected_routes_require_a_valid_token(client, path):
    assert client.get(path).status_code == 401
    assert (
        client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 422
    )


@pytest.mark.parametrize("identity", ["not-a-uuid", "", "123"])
def test_signed_token_with_invalid_identity_is_rejected(client, identity):
    from flask_jwt_extended import create_access_token

    token = create_access_token(identity=identity)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_wrong_password_does_not_issue_tokens(client):
    register(client)
    response = client.post(
        "/auth/login", json={**REGISTER_PAYLOAD, "password": "incorrect-password"}
    )
    assert response.status_code == 401
    assert response.get_json() == {"message": "Invalid credentials"}


def test_expired_access_token_is_rejected(client):
    from flask_jwt_extended import create_access_token

    tokens = register(client)
    token = create_access_token(
        identity=decode_token(tokens["access_token"])["sub"],
        expires_delta=timedelta(seconds=-1),
    )
    assert (
        client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 401
    )


def test_logout_handles_concurrent_session_revocation(client, monkeypatch):
    from app import extensions

    tokens = register(client)
    token = decode_token(tokens["refresh_token"])
    db.session.add(
        TokenBlocklist(
            jti=token["jti"],
            session_id=token["sid"],
            token_type="refresh",
            user_id=token["sub"],
            expires_at=datetime.fromtimestamp(token["exp"], UTC),
        )
    )
    db.session.commit()
    # Model a request whose revocation check completed before the other logout.
    monkeypatch.setattr(
        extensions.jwt_manager, "_token_in_blocklist_callback", lambda *_: False
    )
    response = client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    assert len(db.session.scalars(select(TokenBlocklist)).all()) == 1


def test_logout_does_not_hide_unrelated_integrity_errors(client, monkeypatch):
    tokens = register(client)
    # Complete scheduled cleanup before simulating an insert failure.
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/auth/me", headers=headers).status_code == 200

    def fail_commit():
        raise IntegrityError("INSERT", {}, Exception("unrelated constraint"))

    monkeypatch.setattr(db.session, "commit", fail_commit)
    with pytest.raises(IntegrityError):
        client.post("/auth/logout", headers=headers)


@pytest.mark.parametrize(
    ("path", "status"), [("/auth/register", 400), ("/auth/login", 401)]
)
def test_deeply_nested_json_returns_client_error(client, path, status):
    response = client.post(
        path,
        data="[" * 100_000 + "]" * 100_000,
        content_type="application/json",
    )
    assert response.status_code == status
    assert response.is_json
