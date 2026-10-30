import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from engine.services import ScannerService
from engine.services.tcp import PortState, TCPPortResult, TCPPortScanner


def test_service_has_tcp_scanner_without_starting_scan():
    service = ScannerService()
    assert isinstance(service.tcp_scanner, TCPPortScanner)


def test_service_collects_results_and_passes_scope():
    scanner = TCPPortScanner(timeout=0.5, concurrency=2, rate_limit=10)
    result = TCPPortResult("127.0.0.1", 8000, PortState.OPEN, "Connection accepted")
    scanner.scan = AsyncMock(return_value=[result])
    service = ScannerService(tcp_scanner=scanner)
    scanner.scan.assert_not_called()

    before = datetime.now(UTC)
    report = asyncio.run(
        service.run_all("127.0.0.1", iter([8000]), allowed_targets=iter(["127.0.0.1"]))
    )

    assert report.results == {"tcp": [result]}
    assert report.target == "127.0.0.1"
    assert before <= report.started_at <= report.completed_at <= datetime.now(UTC)
    assert report.configuration.ports == (8000,)
    assert report.configuration.allowed_targets == ("127.0.0.1",)
    assert report.configuration.timeout == 0.5
    assert report.configuration.concurrency == 2
    assert report.configuration.rate_limit == 10
    scanner.scan.assert_awaited_once_with(
        "127.0.0.1", (8000,), allowed_targets=("127.0.0.1",)
    )


@pytest.mark.parametrize(
    "error", [ValueError("invalid scan"), asyncio.CancelledError()]
)
def test_failed_or_cancelled_scan_propagates_without_report(error):
    scanner = TCPPortScanner()
    scanner.scan = AsyncMock(side_effect=error)
    with pytest.raises(type(error)):
        asyncio.run(
            ScannerService(scanner).run_all(
                "127.0.0.1", [8000], allowed_targets=["127.0.0.1"]
            )
        )
