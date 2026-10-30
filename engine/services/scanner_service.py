"""Coordinate the currently implemented scanners."""

from collections.abc import Iterable

from .tcp import TCPPortResult, TCPPortScanner


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
    ) -> dict[str, list[TCPPortResult]]:
        """Collect TCP results; no scans run during construction or import."""
        return {
            "tcp": await self.tcp_scanner.scan(
                target, ports, allowed_targets=allowed_targets
            )
        }
