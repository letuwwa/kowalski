"""TCP reachability checks using native nonblocking sockets."""

import asyncio
import math
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from ipaddress import IPv4Address


class PortState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TCPPortResult:
    target: str
    port: int
    state: PortState
    evidence: str
    error_number: int | None = None


class TCPPortScanner:
    """Scan explicit ports on one allowed IPv4 address without sending payloads.

    Concurrency bounds active workers; rate_limit bounds connection starts per
    second within each scan call. Avoid simultaneous calls when a shared global
    rate limit is required.
    """

    def __init__(
        self,
        *,
        timeout: float = 1.0,
        concurrency: int = 20,
        rate_limit: float = 100.0,
    ) -> None:
        for name, value in (("timeout", timeout), ("rate_limit", rate_limit)):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a finite positive number")
        if type(concurrency) is not int or concurrency < 1:
            raise ValueError("concurrency must be a positive integer")
        self.timeout = timeout
        self.concurrency = concurrency
        self.rate_limit = rate_limit

    async def scan(
        self,
        target: str,
        ports: Iterable[int],
        *,
        allowed_targets: Iterable[str],
    ) -> list[TCPPortResult]:
        """Return results sorted by port; invalid input makes no connections.

        Scope is an explicit allowlist of literal IPv4 addresses. Hostnames,
        CIDRs and automatic asset discovery are intentionally unsupported.
        Cancellation propagates and closes all in-flight sockets.
        """
        address = IPv4Address(target)
        scope = frozenset(IPv4Address(item) for item in allowed_targets)
        if address not in scope:
            raise ValueError(f"Target {address} is outside the allowed scope")
        selected_ports: set[int] = set()
        for port in ports:
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError("Ports must be integers between 1 and 65535")
            selected_ports.add(port)
        if not selected_ports:
            raise ValueError("At least one port is required")

        pending = iter(sorted(selected_ports))
        results: list[TCPPortResult] = []
        rate_lock = asyncio.Lock()
        next_start = 0.0
        loop = asyncio.get_running_loop()

        async def worker() -> None:
            nonlocal next_start
            for port in pending:
                async with rate_lock:
                    delay = next_start - loop.time()
                    if delay > 0:
                        await asyncio.sleep(delay)
                    next_start = loop.time() + 1 / self.rate_limit
                results.append(await self._scan_port(address, port, scope))

        async with asyncio.TaskGroup() as group:
            for _ in range(min(self.concurrency, len(selected_ports))):
                group.create_task(worker())

        return sorted(results, key=lambda result: result.port)

    async def _scan_port(
        self, address: IPv4Address, port: int, scope: frozenset[IPv4Address]
    ) -> TCPPortResult:
        # Recheck the actual numeric destination immediately before connecting.
        # AF_INET and a literal address avoid DNS and target changes entirely.
        if address not in scope:
            raise ValueError(f"Target {address} is outside the allowed scope")
        target = str(address)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
                connection.setblocking(False)
                async with asyncio.timeout(self.timeout):
                    await asyncio.get_running_loop().sock_connect(
                        connection, (target, port)
                    )
        except ConnectionRefusedError as error:
            return TCPPortResult(
                target, port, PortState.CLOSED, "Connection refused", error.errno
            )
        except TimeoutError as error:
            return TCPPortResult(
                target, port, PortState.UNKNOWN, "Connection timed out", error.errno
            )
        except OSError as error:
            return TCPPortResult(
                target, port, PortState.UNKNOWN, str(error), error.errno
            )
        return TCPPortResult(target, port, PortState.OPEN, "Connection accepted")
