from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError

from app import extensions


def test_cleanup_failure_rolls_back_and_releases_lock(app, monkeypatch):
    cleanup = Mock(side_effect=OperationalError("DELETE", {}, Exception("unavailable")))
    rollback = Mock(wraps=extensions.db.session.rollback)
    monkeypatch.setattr(extensions, "cleanup_expired_tokens", cleanup)
    monkeypatch.setattr(extensions.db.session, "rollback", rollback)

    with pytest.raises(OperationalError):
        extensions._cleanup_expired_tokens_if_due()
    rollback.assert_called_once()
    assert "token_blocklist_cleanup_after" not in app.extensions

    cleanup.side_effect = None
    cleanup.return_value = 0
    extensions._cleanup_expired_tokens_if_due()
    assert cleanup.call_count == 2
    extensions._cleanup_expired_tokens_if_due()
    assert cleanup.call_count == 2


def test_cleanup_cli_reports_result(app):
    result = app.test_cli_runner().invoke(args=["cleanup-token-blocklist"])
    assert result.exit_code == 0
    assert "Deleted 0 expired token revocation record(s)." in result.output


def test_cleanup_handles_loaded_revocations(app):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import inspect

    from app.models import TokenBlocklist

    expired = TokenBlocklist(
        jti="loaded-expired",
        token_type="access",
        user_id="user",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    active = TokenBlocklist(
        jti="loaded-active",
        token_type="access",
        user_id="user",
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    extensions.db.session.add_all([expired, active])
    extensions.db.session.commit()
    # SQLite reloads DateTime columns without timezone information.
    assert expired.expires_at < active.expires_at

    assert extensions.cleanup_expired_tokens() == 1
    assert inspect(expired).detached
    assert extensions.db.session.get(TokenBlocklist, active.id) is active


@pytest.mark.parametrize("leeway", [30, 30.0, "timedelta"])
def test_cleanup_respects_supported_clock_leeway_types(app, monkeypatch, leeway):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.models import TokenBlocklist

    now = datetime(2026, 1, 1, tzinfo=UTC)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz)

    monkeypatch.setattr(extensions, "datetime", FrozenDatetime)
    app.config["JWT_DECODE_LEEWAY"] = (
        timedelta(seconds=30) if leeway == "timedelta" else leeway
    )
    for jti, age in [("within-leeway", 29), ("at-expiry", 30)]:
        extensions.db.session.add(
            TokenBlocklist(
                jti=jti,
                token_type="access",
                user_id="user",
                expires_at=now - timedelta(seconds=age),
            )
        )
    extensions.db.session.commit()

    assert extensions.cleanup_expired_tokens() == 1
    assert list(extensions.db.session.scalars(select(TokenBlocklist.jti))) == [
        "within-leeway"
    ]
