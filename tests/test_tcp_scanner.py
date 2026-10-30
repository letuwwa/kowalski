import asyncio
import errno
import socket
from itertools import pairwise
from unittest.mock import AsyncMock

import pytest

from engine.services.tcp import PortState, TCPPortScanner

TARGET = "127.0.0.1"


@pytest.mark.parametrize(
    "options",
    [
        {"timeout": 0},
        {"timeout": -1},
        {"timeout": float("nan")},
        {"timeout": float("inf")},
        {"timeout": True},
        {"rate_limit": 0},
        {"rate_limit": "10"},
        {"rate_limit": float("inf")},
        {"concurrency": 0},
        {"concurrency": 1.5},
        {"concurrency": True},
    ],
)
def test_invalid_configuration(options):
    with pytest.raises(ValueError):
        TCPPortScanner(**options)


@pytest.mark.parametrize(
    "target, ports, scope",
    [
        ("localhost", [80], [TARGET]),
        ("::1", [80], [TARGET]),
        (TARGET, [80], []),
        (TARGET, [80], ["127.0.0.2"]),
        (TARGET, [80], ["127.0.0.0/8"]),
        (TARGET, [], [TARGET]),
        (TARGET, [80, 0], [TARGET]),
        (TARGET, [65536], [TARGET]),
        (TARGET, [True], [TARGET]),
        (TARGET, ["80"], [TARGET]),
    ],
)
def test_invalid_inputs_make_no_connections(monkeypatch, target, ports, scope):
    async def scenario():
        connect = AsyncMock()
        monkeypatch.setattr(asyncio.get_running_loop(), "sock_connect", connect)
        with pytest.raises(ValueError):
            await TCPPortScanner().scan(target, ports, allowed_targets=scope)
        connect.assert_not_awaited()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "error, state, evidence",
    [
        (None, PortState.OPEN, "Connection accepted"),
        (
            ConnectionRefusedError(errno.ECONNREFUSED, "refused"),
            PortState.CLOSED,
            "Connection refused",
        ),
        (TimeoutError(), PortState.UNKNOWN, "Connection timed out"),
        (
            OSError(errno.ENETUNREACH, "Network unreachable"),
            PortState.UNKNOWN,
            "Network unreachable",
        ),
    ],
)
def test_observed_states_and_socket_cleanup(monkeypatch, error, state, evidence):
    async def scenario():
        connections = []

        async def connect(connection, destination):
            assert destination == (TARGET, 8000)
            assert not connection.getblocking()
            connections.append(connection)
            if error is not None:
                raise error

        monkeypatch.setattr(asyncio.get_running_loop(), "sock_connect", connect)
        results = await TCPPortScanner().scan(TARGET, [8000], allowed_targets=[TARGET])
        assert len(results) == 1
        result = results[0]
        assert result.target == TARGET
        assert result.port == 8000
        assert result.state == state
        assert evidence in result.evidence
        assert result.error_number == (error.errno if error else None)
        assert connections[0].fileno() == -1

    asyncio.run(scenario())


def test_timeout_and_cancellation_close_sockets(monkeypatch):
    async def scenario():
        connections = []
        started = asyncio.Event()

        async def connect(connection, destination):
            connections.append(connection)
            started.set()
            await asyncio.Future()

        monkeypatch.setattr(asyncio.get_running_loop(), "sock_connect", connect)
        results = await TCPPortScanner(timeout=0.01).scan(
            TARGET, [8000], allowed_targets=[TARGET]
        )
        assert results[0].state == PortState.UNKNOWN
        assert results[0].evidence == "Connection timed out"
        assert connections[0].fileno() == -1

        started.clear()
        task = asyncio.create_task(
            TCPPortScanner(timeout=10).scan(
                TARGET, [8000, 8001], allowed_targets=[TARGET]
            )
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert all(connection.fileno() == -1 for connection in connections)

    asyncio.run(scenario())


def test_bounded_workers_and_sorted_unique_results(monkeypatch):
    async def scenario():
        active = 0
        peak = 0
        worker_tasks = set()

        async def connect(connection, destination):
            nonlocal active, peak
            worker_tasks.add(asyncio.current_task())
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.005)
            finally:
                active -= 1

        monkeypatch.setattr(asyncio.get_running_loop(), "sock_connect", connect)
        results = await TCPPortScanner(concurrency=3, rate_limit=10000).scan(
            TARGET,
            [8002, 8000, 8002, 8001, *range(8003, 8020)],
            allowed_targets=[TARGET],
        )
        assert [result.port for result in results] == list(range(8000, 8020))
        assert peak == 3
        assert len(worker_tasks) == 3
        assert active == 0

    asyncio.run(scenario())


def test_rate_limit_spaces_connection_starts(monkeypatch):
    async def scenario():
        loop = asyncio.get_running_loop()
        starts = []

        async def connect(connection, destination):
            starts.append(loop.time())

        monkeypatch.setattr(loop, "sock_connect", connect)
        await TCPPortScanner(concurrency=3, rate_limit=50).scan(
            TARGET, [8000, 8001, 8002], allowed_targets=[TARGET]
        )
        assert len(starts) == 3
        assert all(b - a >= 0.018 for a, b in pairwise(starts))

    asyncio.run(scenario())


def test_unexpected_errors_propagate_and_close_sockets(monkeypatch):
    async def scenario():
        connections = []

        async def connect(connection, destination):
            connections.append(connection)
            raise RuntimeError("unexpected failure")

        monkeypatch.setattr(asyncio.get_running_loop(), "sock_connect", connect)
        with pytest.raises(ExceptionGroup) as caught:
            await TCPPortScanner().scan(TARGET, [8000], allowed_targets=[TARGET])
        assert isinstance(caught.value.exceptions[0], RuntimeError)
        assert connections[0].fileno() == -1

    asyncio.run(scenario())


def test_local_open_and_closed_ports():
    async def scenario():
        loop = asyncio.get_running_loop()
        # Keep the refused port bound but not listening to avoid a reuse race.
        with (
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener,
            socket.socket(socket.AF_INET, socket.SOCK_STREAM) as closed,
        ):
            listener.bind((TARGET, 0))
            listener.listen()
            listener.setblocking(False)
            closed.bind((TARGET, 0))
            open_port = listener.getsockname()[1]
            closed_port = closed.getsockname()[1]
            results = await TCPPortScanner().scan(
                TARGET, [open_port, closed_port], allowed_targets=[TARGET]
            )
            states = {result.port: result.state for result in results}
            assert states == {
                open_port: PortState.OPEN,
                closed_port: PortState.CLOSED,
            }
            async with asyncio.timeout(1):
                connection, _ = await loop.sock_accept(listener)
                with connection:
                    connection.setblocking(False)
                    assert await loop.sock_recv(connection, 1) == b""

    asyncio.run(scenario())
