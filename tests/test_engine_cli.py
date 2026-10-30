import json
import socket
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from typer.testing import CliRunner

from engine import scan as cli
from engine.report import ScanConfiguration, ScanReport
from engine.services.tcp import PortState, TCPPortResult

runner = CliRunner()
ARGS = ["127.0.0.1", "--allow-ip", "127.0.0.1", "--ports", "8000"]


def test_cli_passes_options_and_displays_results(monkeypatch):
    service = Mock()
    service.run_all = AsyncMock(
        return_value=ScanReport(
            target="127.0.0.1",
            configuration=ScanConfiguration((8000,), ("127.0.0.1",), 0.5, 2, 10),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            results={
                "tcp": [
                    TCPPortResult(
                        "127.0.0.1", 8000, PortState.OPEN, "Connection accepted"
                    )
                ]
            },
        )
    )
    factory = Mock(return_value=service)
    monkeypatch.setattr(cli, "ScannerService", factory)
    result = runner.invoke(
        cli.app,
        [
            "127.0.0.1",
            "--ports",
            "8001,8000-8002,8000",
            "--allow-ip",
            "127.0.0.1",
            "--allow-ip",
            "127.0.0.2",
            "--timeout",
            "0.5",
            "--concurrency",
            "2",
            "--rate-limit",
            "10",
            "--no-color",
        ],
    )
    assert result.exit_code == 0, result.output
    service.run_all.assert_awaited_once_with(
        "127.0.0.1", [8000, 8001, 8002], allowed_targets=["127.0.0.1", "127.0.0.2"]
    )
    scanner = factory.call_args.kwargs["tcp_scanner"]
    assert (scanner.timeout, scanner.concurrency, scanner.rate_limit) == (0.5, 2, 10)
    assert "open" in result.output
    assert "Connection accepted" in result.output
    assert "Scanned 1 ports." in result.output
    assert "\x1b[" not in result.output


@pytest.mark.parametrize("ports", ["", "0", "65536", "80-22", "22,", "abc", "1-2-3"])
def test_cli_rejects_bad_ports_before_service_creation(monkeypatch, ports):
    factory = Mock()
    monkeypatch.setattr(cli, "ScannerService", factory)
    result = runner.invoke(cli.app, [*ARGS[:-1], ports])
    assert result.exit_code == 2
    assert "--ports" in result.output
    factory.assert_not_called()


@pytest.mark.parametrize(
    "args",
    [
        ["127.0.0.1", "--ports", "80"],
        ["localhost", "--allow-ip", "127.0.0.1", "--ports", "80"],
        ["127.0.0.2", "--allow-ip", "127.0.0.1", "--ports", "80"],
        [*ARGS, "--timeout", "0"],
        [*ARGS, "--concurrency", "0"],
        [*ARGS, "--rate-limit", "nan"],
    ],
)
def test_cli_rejects_invalid_scope_or_configuration(args):
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 2


def test_cli_help_does_not_scan(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(cli, "ScannerService", factory)
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    assert "--allow-ip" in result.output
    factory.assert_not_called()


def test_cli_cancellation(monkeypatch):
    service = Mock()
    service.run_all = AsyncMock(side_effect=KeyboardInterrupt)
    monkeypatch.setattr(cli, "ScannerService", Mock(return_value=service))
    result = runner.invoke(cli.app, ARGS)
    assert result.exit_code == 130
    assert "Scan cancelled." in result.output


def test_cli_scans_local_listener():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        result = runner.invoke(cli.app, [*ARGS[:-1], str(port), "--no-color"])
    assert result.exit_code == 0, result.output
    assert str(port) in result.output
    assert "open" in result.output
    assert "Connection accepted" in result.output


def test_cli_json_is_clean_and_contains_report(monkeypatch):
    service = Mock()
    service.run_all = AsyncMock(
        return_value=ScanReport(
            target="127.0.0.1",
            configuration=ScanConfiguration((8000,), ("127.0.0.1",), 1, 20, 100),
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            results={
                "tcp": [
                    TCPPortResult("127.0.0.1", 8000, PortState.UNKNOWN, "Timed out")
                ]
            },
        )
    )
    monkeypatch.setattr(cli, "ScannerService", Mock(return_value=service))
    result = runner.invoke(cli.app, [*ARGS, "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["target"] == "127.0.0.1"
    assert payload["results"]["tcp"][0]["state"] == "unknown"
    assert payload["summary"]["tcp"]["unknown"] == 1
    assert result.stderr == ""


def test_cli_rejects_unknown_output_format(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(cli, "ScannerService", factory)
    result = runner.invoke(cli.app, [*ARGS, "--format", "xml"])
    assert result.exit_code == 2
    factory.assert_not_called()
