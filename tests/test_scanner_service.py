import asyncio
from unittest.mock import AsyncMock

from engine.services import ScannerService
from engine.services.tcp import PortState, TCPPortResult, TCPPortScanner


def test_service_has_tcp_scanner_without_starting_scan():
    service = ScannerService()
    assert isinstance(service.tcp_scanner, TCPPortScanner)


def test_service_collects_results_and_passes_scope():
    scanner = AsyncMock(spec=TCPPortScanner)
    result = TCPPortResult("127.0.0.1", 8000, PortState.OPEN, "Connection accepted")
    scanner.scan.return_value = [result]
    service = ScannerService(tcp_scanner=scanner)
    scanner.scan.assert_not_called()

    results = asyncio.run(
        service.run_all("127.0.0.1", [8000], allowed_targets=["127.0.0.1"])
    )

    assert results == {"tcp": [result]}
    scanner.scan.assert_awaited_once_with(
        "127.0.0.1", [8000], allowed_targets=["127.0.0.1"]
    )
