"""Coordinate the currently implemented scanners."""

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from engine.report import ScanConfiguration, ScanReport
from engine.targets import normalize_target, resolve_ipv4

from .tcp import TCPPortScanner
from .tcp.scanner import validate_ports


class ScannerService:
    """Run available scanners and collect their results by scanner name.

    Only TCP is implemented today. Keep explicit composition until additional
    scanners demonstrate a need for a shared plugin interface.
    """

    def __init__(self, tcp_scanner: TCPPortScanner | None = None) -> None:
        self.tcp_scanner = tcp_scanner if tcp_scanner is not None else TCPPortScanner()

    async def run_all(
        self,
        target: str,
        ports: Iterable[int],
        *,
        allowed_targets: Iterable[str],
        report_id: UUID | None = None,
    ) -> ScanReport:
        """Collect TCP results; no scans run during construction or import."""
        target = normalize_target(target)
        selected_ports = validate_ports(ports)
        scope = tuple(normalize_target(item) for item in allowed_targets)
        if target not in scope:
            raise ValueError(f"Target {target} is outside the allowed scope")
        started_at = datetime.now(UTC)
        addresses = await resolve_ipv4(target)
        configuration = ScanConfiguration(
            ports=selected_ports,
            allowed_targets=scope,
            timeout=self.tcp_scanner.timeout,
            concurrency=self.tcp_scanner.concurrency,
            rate_limit=self.tcp_scanner.rate_limit,
        )
        results = []
        for index, address in enumerate(addresses):
            if index:
                # Keep the rate bound across separate address scans as well.
                await asyncio.sleep(1 / self.tcp_scanner.rate_limit)
            results.extend(
                await self.tcp_scanner.scan(
                    address, selected_ports, allowed_targets=addresses
                )
            )
        return ScanReport(
            id=report_id if report_id is not None else uuid4(),
            target=target,
            configuration=configuration,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            results={"tcp": results},
        )
