import asyncio
import base64
from unittest.mock import AsyncMock

import pytest

from core.report import ServiceObservation
from core.services import ScannerService
from core.services.ssh import MAX_BANNER_BYTES, identify_ssh
from core.services.tcp import PortState, TCPPortResult, TCPPortScanner


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
    monkeypatch.setattr("core.services.scanner_service.resolve_ipv4", lookup)
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
    monkeypatch.setattr("core.services.scanner_service.identify_ssh", identifier)
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
