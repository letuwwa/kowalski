import asyncio
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import OperationalError

from app import worker
from app.extensions import db
from app.models import ScanJob, ScanRun, TCPPortResult, User
from app.services.reports import store_report
from engine.report import ScanConfiguration, ScanReport
from engine.services.tcp import PortState
from engine.services.tcp import TCPPortResult as Observation

PAYLOAD = {"target": "127.0.0.1", "ports": [22, 80], "scanners": ["tcp"]}


@pytest.fixture
def users(app):
    rows = [
        User(
            email=f"owner{index}@example.test",
            username=f"owner{index}",
            first_name="Scan",
            last_name="Owner",
            password_hash="unused",
        )
        for index in range(2)
    ]
    db.session.add_all(rows)
    db.session.commit()
    return rows


def headers(user):
    return {
        "Authorization": f"Bearer {create_access_token(identity=str(inspect(user).identity[0]))}"
    }


def make_report(*, identifier=None, when=None, ports=None, target="127.0.0.1"):
    when = when or datetime.now(UTC)
    ports = ports if ports is not None else {22: "open", 80: "closed"}
    return ScanReport(
        id=identifier or uuid.uuid4(),
        target=target,
        started_at=when,
        completed_at=when + timedelta(seconds=1),
        configuration=ScanConfiguration(tuple(sorted(ports)), (target,), 1, 20, 100),
        results={
            "tcp": [
                Observation(target, port, PortState(state), f"Observed {state}")
                for port, state in sorted(ports.items())
            ]
        },
    )


@pytest.fixture
def fake_execution(monkeypatch):
    async def execute(job_id, target, config):
        report = make_report(
            identifier=job_id,
            target=target,
            ports={port: "open" for port in config["ports"]},
        )
        report.configuration = ScanConfiguration(
            tuple(config["ports"]),
            tuple(config["allowed_targets"]),
            config["timeout"],
            config["concurrency"],
            config["rate_limit"],
        )
        return report

    mock = AsyncMock(side_effect=execute)
    monkeypatch.setattr(worker, "execute_scan", mock)
    return mock


def test_submission_returns_202_without_network_and_worker_saves_report(
    client, users, fake_execution
):
    auth = headers(users[0])
    response = client.post("/scans", json=PAYLOAD, headers=auth)
    assert response.status_code == 202
    job_id = response.json["id"]
    assert response.headers["Location"] == f"/scans/{job_id}"
    assert response.json["status"] == "queued"
    fake_execution.assert_not_awaited()
    assert worker.work_once()
    fake_execution.assert_awaited_once()
    response = client.get(f"/scans/{job_id}", headers=auth)
    assert response.status_code == 200
    assert response.json["status"] == "completed"
    assert response.json["report"]["id"] == job_id
    assert response.json["report"]["summary"]["tcp"]["open"] == 2
    assert response.json["report"]["configuration"]["allowed_targets"] == ["127.0.0.1"]
    assert response.headers["Cache-Control"] == "no-store"
    assert db.session.scalar(select(func.count()).select_from(ScanRun)) == 1
    assert db.session.scalar(select(func.count()).select_from(TCPPortResult)) == 2
    assert not worker.work_once()


@pytest.mark.parametrize(
    "method,url",
    [
        ("post", "/scans"),
        ("get", "/scans"),
        ("get", "/scans/history?target=127.0.0.1"),
        ("get", f"/scans/{uuid.uuid4()}"),
    ],
)
def test_all_endpoints_require_authentication(client, method, url):
    assert getattr(client, method)(url).status_code == 401


def test_other_users_cannot_read_jobs_or_history(client, users, fake_execution):
    response = client.post("/scans", json=PAYLOAD, headers=headers(users[0]))
    job_id = response.json["id"]
    worker.work_once()
    auth = headers(users[1])
    assert client.get(f"/scans/{job_id}", headers=auth).status_code == 404
    assert client.get("/scans", headers=auth).json["items"] == []
    assert (
        client.get("/scans/history?target=127.0.0.1", headers=auth).json["items"] == []
    )
    assert client.get(f"/scans/{uuid.uuid4()}", headers=auth).status_code == 404


@pytest.mark.parametrize(
    "override,status",
    [
        ({"target": "localhost"}, 400),
        ({"target": "::1"}, 400),
        ({"target": 1}, 400),
        ({"ports": []}, 400),
        ({"ports": [0]}, 400),
        ({"ports": [65536]}, 400),
        ({"ports": [True]}, 400),
        ({"ports": "22-80"}, 400),
        ({"ports": list(range(1, 1026))}, 400),
        ({"scanners": ["http"]}, 400),
        ({"scanners": []}, 400),
        ({"timeout": 0}, 400),
        ({"timeout": 6}, 400),
        ({"timeout": True}, 400),
        ({"timeout": "1"}, 400),
        ({"timeout": 10**1000}, 400),
        ({"concurrency": 21}, 400),
        ({"concurrency": 1.5}, 400),
        ({"rate_limit": 101}, 400),
        ({"rate_limit": -1}, 400),
        ({"user_id": str(uuid.uuid4())}, 400),
        ({"allowed_targets": ["192.0.2.1"]}, 400),
    ],
)
def test_submission_validation_prevents_unauthorized_or_unbounded_work(
    client, users, override, status
):
    response = client.post(
        "/scans", json={**PAYLOAD, **override}, headers=headers(users[0])
    )
    assert response.status_code == status
    assert "message" in response.json
    assert db.session.scalar(select(func.count()).select_from(ScanJob)) == 0


@pytest.mark.parametrize("body", ["[]", "null", "bad json", "[" * 1500 + "]" * 1500])
def test_bad_json_is_a_client_error(client, users, body):
    response = client.post(
        "/scans", data=body, content_type="application/json", headers=headers(users[0])
    )
    assert response.status_code == 400


def test_queue_limits_and_disabled_users(client, users, app):
    app.config["SCAN_MAX_PENDING_PER_USER"] = 1
    auth = headers(users[0])
    assert client.post("/scans", json=PAYLOAD, headers=auth).status_code == 202
    assert client.post("/scans", json=PAYLOAD, headers=auth).status_code == 429
    app.config["SCAN_MAX_PENDING"] = 1
    assert (
        client.post("/scans", json=PAYLOAD, headers=headers(users[1])).status_code
        == 429
    )
    users[0].is_active = False
    db.session.commit()
    assert client.get("/scans", headers=auth).status_code == 403
    assert worker.work_once()
    assert db.session.scalar(select(ScanJob)).error == "Scan owner is disabled"


def test_list_keyset_pagination_filters_and_validation(client, users):
    auth = headers(users[0])
    ids = [
        client.post("/scans", json=PAYLOAD, headers=auth).json["id"] for _ in range(3)
    ]
    first = client.get(
        "/scans?limit=2&status=queued&target=127.0.0.1", headers=auth
    ).json
    assert len(first["items"]) == 2
    second = client.get(
        "/scans",
        query_string={"limit": 2, "cursor": first["next_cursor"]},
        headers=auth,
    ).json
    assert second["next_cursor"] is None
    assert {row["id"] for row in first["items"] + second["items"]} == set(ids)
    assert client.get("/scans?status=completed", headers=auth).json["items"] == []
    for query in (
        "limit=0",
        "limit=101",
        "limit=abc",
        "cursor=bad",
        "status=bad",
        "target=localhost",
    ):
        assert client.get(f"/scans?{query}", headers=auth).status_code == 400
    assert client.get("/scans/not-a-uuid", headers=auth).status_code == 400


def test_history_over_multiple_scans_with_gaps_unknowns_and_continuous_pagination(
    client, users
):
    when = datetime(2026, 1, 1, tzinfo=UTC)
    reports = [
        make_report(
            identifier=uuid.UUID(int=index + 1),
            when=when + timedelta(days=index),
            ports=ports,
        )
        for index, ports in enumerate(
            [
                {22: "closed", 80: "open"},
                {22: "open", 80: "unknown", 443: "open"},
                {22: "open", 443: "closed"},
            ]
        )
    ]
    for report in reports:
        store_report(report, users[0].id)
    # These observations must never become the baseline for the owner's target.
    store_report(make_report(when=when + timedelta(hours=12)), users[1].id)
    store_report(
        make_report(target="127.0.0.2", when=when + timedelta(hours=12)), users[0].id
    )
    db.session.commit()
    auth = headers(users[0])
    first = client.get("/scans/history?target=127.0.0.1&limit=2", headers=auth).json
    assert len(first["items"]) == 2
    assert first["items"][0]["baseline_id"] is None
    changes = first["items"][1]["changes"]
    assert changes == [
        {"port": 22, "previous": "closed", "current": "open", "kind": "state_changed"},
        {"port": 80, "previous": "open", "current": "unknown", "kind": "inconclusive"},
    ]
    assert first["items"][1]["only_in_current"] == [443]
    assert first["items"][1]["configuration_changed"]
    second = client.get(
        "/scans/history",
        query_string={
            "target": "127.0.0.1",
            "cursor": first["next_cursor"],
            "limit": 2,
        },
        headers=auth,
    ).json
    item = second["items"][0]
    assert item["baseline_id"] == str(reports[1].id)
    assert item["only_in_previous"] == [80]
    assert item["changes"] == [
        {"port": 443, "previous": "open", "current": "closed", "kind": "state_changed"}
    ]
    assert second["next_cursor"] is None
    filtered = client.get(
        "/scans/history",
        query_string={
            "target": "127.0.0.1",
            "from": reports[1].started_at.isoformat(),
            "to": reports[1].started_at.isoformat(),
        },
        headers=auth,
    ).json
    assert len(filtered["items"]) == 1
    assert filtered["items"][0]["baseline_id"] == str(reports[0].id)


@pytest.mark.parametrize(
    "query",
    [
        {},
        {"target": "localhost"},
        {"target": "127.0.0.1", "from": "2026-01-01"},
        {"target": "127.0.0.1", "from": "bad"},
        {
            "target": "127.0.0.1",
            "from": "2026-02-01T00:00:00Z",
            "to": "2026-01-01T00:00:00Z",
        },
    ],
)
def test_history_rejects_invalid_filters(client, users, query):
    assert (
        client.get(
            "/scans/history", query_string=query, headers=headers(users[0])
        ).status_code
        == 400
    )


def test_report_retries_conflicts_and_rollback(users):
    report = make_report()
    run = store_report(report, users[0].id)
    db.session.commit()
    assert store_report(report, users[0].id).id == run.id
    with pytest.raises(ValueError, match="conflicts"):
        store_report(report, users[1].id)
    report.results["tcp"][0] = Observation(
        report.target, 22, PortState.CLOSED, "Changed evidence"
    )
    with pytest.raises(ValueError, match="conflicts"):
        store_report(report, users[0].id)
    db.session.rollback()
    other = make_report()
    other_id = other.id
    store_report(other, users[0].id)
    db.session.rollback()
    assert db.session.get(ScanRun, other_id) is None


@pytest.mark.parametrize("failure", [RuntimeError("secret detail"), TimeoutError()])
def test_worker_failure_is_recorded_without_report_or_sensitive_error(
    client, users, monkeypatch, failure
):
    response = client.post("/scans", json=PAYLOAD, headers=headers(users[0]))
    monkeypatch.setattr(worker, "execute_scan", AsyncMock(side_effect=failure))
    assert worker.work_once()
    job = db.session.get(ScanJob, uuid.UUID(response.json["id"]))
    assert job.status == "failed"
    assert "secret detail" not in job.error
    assert db.session.get(ScanRun, job.id) is None


def test_worker_revalidates_limits_and_recovers_abandoned_jobs(
    client, users, fake_execution, app
):
    job_id = client.post("/scans", json=PAYLOAD, headers=headers(users[0])).json["id"]
    app.config["SCAN_MAX_PORTS"] = 1
    assert worker.work_once()
    fake_execution.assert_not_awaited()
    job = db.session.get(ScanJob, uuid.UUID(job_id))
    assert job.status == "failed"
    job.status = "running"
    db.session.commit()
    assert not worker.work_once()
    assert (
        db.session.get(ScanJob, job.id).error == "Worker stopped before scan completion"
    )


def test_storage_failure_rolls_back_report_and_marks_job_failed(
    client, users, fake_execution, monkeypatch
):
    job_id = client.post("/scans", json=PAYLOAD, headers=headers(users[0])).json["id"]

    def broken_store(*args):
        store_report(*args)
        raise OperationalError("insert", {}, Exception("database unavailable"))

    monkeypatch.setattr(worker, "store_report", broken_store)
    assert worker.work_once()
    assert db.session.get(ScanJob, uuid.UUID(job_id)).status == "failed"
    assert db.session.get(ScanRun, uuid.UUID(job_id)) is None
    assert db.session.scalar(select(func.count()).select_from(TCPPortResult)) == 0


def test_internet_target_needs_no_predefined_allowlist(client, users, fake_execution):
    auth = headers(users[0])
    response = client.post(
        "/scans", json={**PAYLOAD, "target": "93.184.216.34"}, headers=auth
    )
    assert response.status_code == 202
    assert worker.work_once()
    fake_execution.assert_awaited_once()
    target = fake_execution.call_args.args[1]
    config = fake_execution.call_args.args[2]
    assert target == "93.184.216.34"
    assert config["allowed_targets"] == [target]
    result = client.get(response.headers["Location"], headers=auth)
    assert result.json["status"] == "completed"
    assert result.json["report"]["target"] == target


def test_worker_timeout_cleans_up_running_coroutine(client, users, monkeypatch, app):
    app.config["SCAN_JOB_TIMEOUT"] = 0.01
    cancelled = []

    async def blocked(*args, **kwargs):
        try:
            await asyncio.Future()
        finally:
            cancelled.append(True)

    monkeypatch.setattr(worker.ScannerService, "run_all", blocked)
    job_id = client.post("/scans", json=PAYLOAD, headers=headers(users[0])).json["id"]
    assert worker.work_once()
    assert cancelled == [True]
    assert db.session.get(ScanJob, uuid.UUID(job_id)).status == "failed"


def test_worker_lock_and_command_once(app, monkeypatch):
    @contextmanager
    def busy():
        yield False

    monkeypatch.setattr(worker, "worker_lock", busy)
    assert not worker.work_once()
    result = app.test_cli_runner().invoke(args=["scan-worker", "--once"])
    assert result.exit_code == 0, result.output


def test_storage_error_is_json_503(client, users, monkeypatch):
    def broken_submit(*args):
        raise OperationalError("insert", {}, Exception("secret database credentials"))

    monkeypatch.setattr("app.routers.scans.submit_scan", broken_submit)
    response = client.post("/scans", json=PAYLOAD, headers=headers(users[0]))
    assert response.status_code == 503
    assert response.json == {"message": "Scan storage is unavailable"}


def test_api_worker_end_to_end_with_local_tcp_listener(client, users):
    auth = headers(users[0])
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        response = client.post(
            "/scans", json={**PAYLOAD, "ports": [port]}, headers=auth
        )
        assert response.status_code == 202
        job_id = response.json["id"]
        assert worker.work_once()
    stored = client.get(f"/scans/{job_id}", headers=auth)
    assert stored.json["status"] == "completed"
    assert stored.json["report"]["id"] == job_id
    assert stored.json["report"]["results"]["tcp"][0]["state"] == "open"


def test_postgres_worker_lock_prevents_overlapping_workers(
    client, users, fake_execution
):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL session advisory lock")
    client.post("/scans", json=PAYLOAD, headers=headers(users[0]))
    with db.engine.connect().execution_options(
        isolation_level="AUTOCOMMIT"
    ) as connection:
        connection.execute(text("SELECT pg_advisory_lock(67204201)"))
        try:
            assert not worker.work_once()
            fake_execution.assert_not_awaited()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(67204201)"))
    assert worker.work_once()


def test_postgres_concurrent_requests_respect_queue_quota(app, users):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL transaction advisory lock")
    app.config["SCAN_MAX_PENDING_PER_USER"] = 1
    auth = headers(users[0])

    def submit(_):
        with app.test_client() as client:
            return client.post("/scans", json=PAYLOAD, headers=auth).status_code

    db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submit, range(2)))
    assert sorted(results) == [202, 429]


def test_postgres_concurrent_report_saves_are_idempotent(app, users):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL concurrent inserts")
    owner_id = users[0].id
    report = make_report()
    db.session.remove()

    def save(_):
        with app.app_context():
            run = store_report(report, owner_id)
            identifier = run.id
            db.session.commit()
            return identifier

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save, range(2)))
    assert results == [report.id, report.id]
    assert db.session.scalar(select(func.count()).select_from(ScanRun)) == 1
