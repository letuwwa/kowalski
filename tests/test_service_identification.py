import asyncio
import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import worker
from app.extensions import db
from app.models import ScanJob, ScanRun, User
from app.services.reports import report_from_run, store_report
from app.services.scans import history, service_changes, validate_scan
from engine.report import ScanConfiguration, ScanReport, ServiceObservation
from engine.services import ScannerService
from engine.services.ssh import MAX_BANNER_BYTES, identify_ssh
from engine.services.tcp import PortState, TCPPortResult, TCPPortScanner


@pytest.mark.parametrize(
    "chunks,status,software,error",
    [
        ([b"SSH-2.0-OpenSSH_9.6 Ubuntu\r\n"], "identified", "OpenSSH_9.6", None),
        (
            [b"Welcome\r\nSS", b"H-2.0-Example", b"_1\r", b"\n"],
            "identified",
            "Example_1",
            None,
        ),
        ([b"SSH-1.99-Example\n"], "identified", "Example", None),
        ([b"SSH-1.5-OldSSH\r\n"], "identified", "OldSSH", None),
        ([b"SSH-2.0-\r\n"], "unidentified", None, "Malformed"),
        ([b"SSH-2.0-bad-name\r\n"], "unidentified", None, "Malformed"),
        ([b"SSH-2.0-bad\x00\r\n"], "unidentified", None, "Malformed"),
        ([b"SSH-2.0-" + b"a" * 250 + b"\r\n"], "unidentified", None, "Malformed"),
        ([b"HTTP/1.1 200 OK\r\n"], "unidentified", None, "closed"),
        ([b"SSH-2.0-Partial"], "unidentified", None, "closed"),
        ([], "unidentified", None, "closed"),
        ([b"x" * (MAX_BANNER_BYTES + 100)], "unidentified", None, "limit"),
    ],
)
def test_local_banner_parsing(chunks, status, software, error):
    async def scenario():
        async def serve(reader, writer):
            try:
                for chunk in chunks:
                    writer.write(chunk)
                    await writer.drain()
                    await asyncio.sleep(0)
            finally:
                writer.close()
                await writer.wait_closed()

        async with await asyncio.start_server(serve, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            row = await identify_ssh(
                "127.0.0.1", port, allowed_targets=("127.0.0.1",), timeout=1
            )
        assert row.status == status
        assert row.advertised_software == software
        evidence = base64.b64decode(row.evidence_base64)
        assert len(evidence) <= MAX_BANNER_BYTES
        assert b"".join(chunks).startswith(evidence)
        if error:
            assert error in row.error
        else:
            assert row.protocol == "ssh"
            assert row.confidence == "high"
            assert row.banner.startswith("SSH-")
            assert row.error is None

    asyncio.run(scenario())


def test_silent_server_timeout_partial_evidence_and_cancellation_cleanup():
    async def scenario():
        disconnected = asyncio.Queue()

        async def serve(reader, writer):
            writer.write(b"Welcome\n")
            await writer.drain()
            try:
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()
                disconnected.put_nowait(True)

        async with await asyncio.start_server(serve, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            row = await identify_ssh(
                "127.0.0.1", port, allowed_targets=("127.0.0.1",), timeout=0.05
            )
            assert row.status == "timeout"
            assert base64.b64decode(row.evidence_base64) == b"Welcome\n"
            await asyncio.wait_for(disconnected.get(), 1)
            task = asyncio.create_task(
                identify_ssh(
                    "127.0.0.1", port, allowed_targets=("127.0.0.1",), timeout=10
                )
            )
            await asyncio.sleep(0.02)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.wait_for(disconnected.get(), 1)

    asyncio.run(scenario())


def test_refused_connection_is_identification_error():
    async def scenario():
        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()
        row = await identify_ssh(
            "127.0.0.1", port, allowed_targets=("127.0.0.1",), timeout=1
        )
        assert row.status == "error"
        assert row.protocol is None

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "target,scope,port,timeout",
    [
        ("example.test", ("127.0.0.1",), 22, 1),
        ("127.0.0.2", ("127.0.0.1",), 22, 1),
        ("127.0.0.1", ("127.0.0.1",), 0, 1),
        ("127.0.0.1", ("127.0.0.1",), 22, 0),
        ("127.0.0.1", ("127.0.0.1",), 22, float("nan")),
    ],
)
def test_invalid_identification_input_never_connects(
    monkeypatch, target, scope, port, timeout
):
    connect = AsyncMock()
    monkeypatch.setattr(asyncio.BaseEventLoop, "sock_connect", connect)
    with pytest.raises(ValueError):
        asyncio.run(identify_ssh(target, port, allowed_targets=scope, timeout=timeout))
    connect.assert_not_awaited()


def test_orchestration_probes_only_selected_open_pinned_destinations(monkeypatch):
    lookup = AsyncMock(return_value=("127.0.0.1", "127.0.0.2"))
    monkeypatch.setattr("engine.services.scanner_service.resolve_ipv4", lookup)
    scanner = TCPPortScanner(rate_limit=1000)

    async def scan(target, ports, **kwargs):
        return [
            TCPPortResult(target, port, state, "Observed")
            for port, state in (
                (22, PortState.OPEN),
                (2222, PortState.OPEN),
                (80, PortState.CLOSED),
                (443, PortState.UNKNOWN),
            )
        ]

    scanner.scan = AsyncMock(side_effect=scan)
    identifier = AsyncMock(
        side_effect=lambda target, port, **kwargs: ServiceObservation(
            target, port, "timeout", ""
        )
    )
    monkeypatch.setattr("engine.services.scanner_service.identify_ssh", identifier)
    report = asyncio.run(
        ScannerService(scanner).run_all(
            "scan.example.test",
            [22, 80, 443, 2222],
            allowed_targets=["scan.example.test"],
            service_ports=[2222, 80, 443],
        )
    )
    lookup.assert_awaited_once()
    assert len(report.services) == 2
    for call in identifier.await_args_list:
        assert call.args[1] == 2222
        assert call.kwargs["allowed_targets"] == ("127.0.0.1", "127.0.0.2")
    assert report.results["tcp"][0].state == PortState.OPEN
    identifier.reset_mock()
    asyncio.run(
        ScannerService(scanner).run_all(
            "scan.example.test",
            [22],
            allowed_targets=["scan.example.test"],
            service_ports=[],
        )
    )
    identifier.assert_not_awaited()


@pytest.mark.parametrize("ports", [None, "22", [0], [True], [65536]])
def test_api_rejects_invalid_service_ports(app, ports):
    from werkzeug.exceptions import BadRequest

    with pytest.raises(BadRequest):
        validate_scan({"target": "127.0.0.1", "ports": [22], "service_ports": ports})


def test_api_worker_persistence_and_chronological_service_changes(app, monkeypatch):
    owner = User(
        email="services@example.test",
        username="services",
        first_name="Test",
        last_name="User",
        password_hash="unused",
    )
    db.session.add(owner)
    db.session.commit()
    owner_id = owner.id
    now = datetime.now(UTC)
    observation = ServiceObservation(
        "127.0.0.1",
        2222,
        "identified",
        "U1NILTIuMC1UZXN0XzENCg==",
        protocol="ssh",
        banner="SSH-2.0-Test_1",
        protocol_version="2.0",
        advertised_software="Test_1",
        confidence="high",
    )
    reports = []
    for index, row in enumerate(
        (
            observation,
            replace(observation, banner="SSH-2.0-Test_2", advertised_software="Test_2"),
            replace(
                observation,
                status="timeout",
                protocol=None,
                confidence=None,
                banner=None,
            ),
        )
    ):
        report = ScanReport(
            target="127.0.0.1",
            configuration=ScanConfiguration(
                (2222,), ("127.0.0.1",), 1, 20, 100, (2222,)
            ),
            started_at=now + timedelta(seconds=index),
            completed_at=now + timedelta(seconds=index),
            results={
                "tcp": [TCPPortResult("127.0.0.1", 2222, PortState.OPEN, "Accepted")]
            },
            services=[row],
        )
        stored = store_report(report, owner_id)
        db.session.commit()
        assert report_from_run(stored).to_dict() == report.to_dict()
        assert store_report(report, owner_id).id == report.id
        reports.append(stored)
    items = history(owner_id, "127.0.0.1", {})["items"]
    assert items[0]["service_changes"] == []
    assert items[1]["service_changes"][0]["kind"] == "banner_changed"
    assert items[2]["service_changes"][0]["kind"] == "inconclusive"
    assert items[2]["changes"] == []
    assert service_changes(SimpleNamespace(services=[]), reports[0]) == []
    assert service_changes(reports[0], SimpleNamespace(services=[])) == []
    target, config = validate_scan(
        {"target": "127.0.0.1", "ports": [2222], "service_ports": [2222]}
    )
    job = ScanJob(user_id=owner_id, target=target, configuration=config)
    db.session.add(job)
    db.session.commit()
    job_id = job.id
    captured = []

    async def run_all(self, target, ports, **kwargs):
        captured.append(kwargs["service_ports"])
        return replace_report(kwargs["report_id"])

    def replace_report(identifier):
        return ScanReport(
            id=identifier,
            target=target,
            configuration=ScanConfiguration((2222,), (target,), 1, 20, 100, (2222,)),
            started_at=now,
            completed_at=now,
            results={"tcp": [TCPPortResult(target, 2222, PortState.OPEN, "Accepted")]},
            services=[observation],
        )

    monkeypatch.setattr(ScannerService, "run_all", run_all)
    assert worker.work_once()
    assert captured == [[2222]]
    assert db.session.get(ScanJob, job_id).status == "completed"
    assert db.session.get(ScanRun, job_id).services[0]["protocol"] == "ssh"


def test_real_tcp_scan_followed_by_receive_only_identification():
    async def scenario():
        received = asyncio.Queue()

        async def serve(reader, writer):
            try:
                writer.write(b"Notice\r\nSSH-2.0-LocalSSH_1 test\r\n")
                await writer.drain()
                received.put_nowait(await reader.read())
            finally:
                writer.close()
                await writer.wait_closed()

        async with await asyncio.start_server(serve, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            report = await ScannerService(TCPPortScanner(timeout=1)).run_all(
                "127.0.0.1", [port], allowed_targets=["127.0.0.1"], service_ports=[port]
            )
            assert report.results["tcp"][0].state == PortState.OPEN
            assert report.services[0].advertised_software == "LocalSSH_1"
            assert report.services[0].banner == "SSH-2.0-LocalSSH_1 test"
            for _ in range(2):
                assert await asyncio.wait_for(received.get(), 1) == b""

    asyncio.run(scenario())


def test_service_migration_preserves_evidence_and_guards_downgrade(app):
    from sqlalchemy import inspect, text

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
        import uuid

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
