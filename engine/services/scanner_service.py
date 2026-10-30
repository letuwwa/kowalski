"""Coordinate the currently implemented scanners."""

from collections.abc import Iterable
from datetime import UTC, datetime

from engine.report import ScanConfiguration, ScanReport

from .tcp import TCPPortScanner


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
    ) -> ScanReport:
        """Collect TCP results; no scans run during construction or import."""
        selected_ports = tuple(ports)
        scope = tuple(allowed_targets)
        started_at = datetime.now(UTC)
        configuration = ScanConfiguration(
            ports=selected_ports,
            allowed_targets=scope,
            timeout=self.tcp_scanner.timeout,
            concurrency=self.tcp_scanner.concurrency,
            rate_limit=self.tcp_scanner.rate_limit,
        )
        results = await self.tcp_scanner.scan(
            target, selected_ports, allowed_targets=scope
        )
        return ScanReport(
            target=target,
            configuration=configuration,
            started_at=started_at,
            completed_at=datetime.now(UTC),
            results={"tcp": results},
        )
