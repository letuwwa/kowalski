import asyncio
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock

import dns.asyncresolver
import dns.exception
import dns.message
import dns.resolver
import dns.rrset
import pytest

from core.services import ScannerService
from core.services.tcp import PortState, TCPPortResult, TCPPortScanner
from core.targets import TargetResolutionError, normalize_target, resolve_ipv4


@pytest.mark.parametrize(
    "value,expected",
    [
        ("127.0.0.1", "127.0.0.1"),
        (" Scan.Example.TEST. ", "scan.example.test"),
        ("BÜCHER.example", "xn--bcher-kva.example"),
        ("localhost", "localhost"),
    ],
)
def test_target_normalization(value, expected):
    assert normalize_target(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        "",
        " ",
        ".",
        "bad..example",
        "bad_name.test",
        "-bad.test",
        "bad-.test",
        "https://example.test/path",
        "example.test:443",
        "example.test/path",
        "::1",
        "999.1.1.1",
        "127.000.0.1",
        "123",
        "*.example.test",
        "a" * 64 + ".test",
        ".".join(["a" * 63] * 4),
        "bad\x00.test",
    ],
)
def test_invalid_targets(value):
    with pytest.raises(ValueError):
        normalize_target(value)


def test_lossy_unicode_mapping_requires_explicit_punycode():
    with pytest.raises(ValueError, match="punycode"):
        normalize_target("faß.example")
    assert normalize_target("xn--fa-hia.example") == "xn--fa-hia.example"


def test_literal_ip_does_not_query_dns(monkeypatch):
    lookup = AsyncMock()
    monkeypatch.setattr(dns.asyncresolver, "resolve", lookup)
    assert asyncio.run(resolve_ipv4("127.0.0.1")) == ("127.0.0.1",)
    lookup.assert_not_called()


def test_resolution_deduplicates_and_sorts_numeric_addresses(monkeypatch):
    lookup = AsyncMock(
        return_value=[
            SimpleNamespace(address=address)
            for address in [
                "127.0.0.10",
                "127.0.0.2",
                "127.0.0.10",
            ]
        ]
    )
    monkeypatch.setattr(dns.asyncresolver, "resolve", lookup)
    assert asyncio.run(resolve_ipv4("Scan.Example.Test.")) == (
        "127.0.0.2",
        "127.0.0.10",
    )
    lookup.assert_awaited_once_with("scan.example.test.", "A", search=False, lifetime=5)


@pytest.mark.parametrize(
    "error,message",
    [
        (dns.resolver.NXDOMAIN(), "does not exist"),
        (dns.resolver.NoAnswer(), "No IPv4"),
        (dns.resolver.NoNameservers(), "resolution failed"),
        (dns.exception.Timeout(), "timed out"),
        (TimeoutError(), "timed out"),
        (OSError("network unreachable"), "resolution failed"),
    ],
)
def test_expected_dns_failures_are_clear(monkeypatch, error, message):
    monkeypatch.setattr(dns.asyncresolver, "resolve", AsyncMock(side_effect=error))
    with pytest.raises(TargetResolutionError, match=message):
        asyncio.run(resolve_ipv4("scan.example.test"))


@pytest.mark.parametrize(
    "addresses,message",
    [
        ([], "No IPv4"),
        (["127.0.0." + str(number) for number in range(1, 10)], "more than 8"),
        (["::1"], "resolution failed"),
    ],
)
def test_no_ipv4_invalid_or_excessive_answers_are_rejected(
    monkeypatch, addresses, message
):
    monkeypatch.setattr(
        dns.asyncresolver,
        "resolve",
        AsyncMock(
            return_value=[SimpleNamespace(address=address) for address in addresses]
        ),
    )
    with pytest.raises(TargetResolutionError, match=message):
        asyncio.run(resolve_ipv4("scan.example.test"))


def test_dns_cancellation_propagates(monkeypatch):
    async def scenario():
        started = asyncio.Event()
        cancelled = []

        async def blocked(*args, **kwargs):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.append(True)

        monkeypatch.setattr(dns.asyncresolver, "resolve", blocked)
        task = asyncio.create_task(resolve_ipv4("scan.example.test"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled == [True]

    asyncio.run(scenario())


def test_service_pins_one_resolution_and_keeps_rate_across_addresses(monkeypatch):
    async def scenario():
        addresses = ("127.0.0.1", "127.0.0.2")
        lookup = AsyncMock(return_value=addresses)
        monkeypatch.setattr("core.services.scanner_service.resolve_ipv4", lookup)
        starts = []
        scanner = TCPPortScanner(rate_limit=50)

        async def scan(address, ports, *, allowed_targets):
            assert address in addresses
            assert allowed_targets == addresses
            starts.append(asyncio.get_running_loop().time())
            return [
                TCPPortResult(address, port, PortState.OPEN, "Accepted")
                for port in ports
            ]

        scanner.scan = AsyncMock(side_effect=scan)
        report = await ScannerService(scanner).run_all(
            "SCAN.example.test.", [443], allowed_targets=["scan.example.test"]
        )
        lookup.assert_awaited_once_with("scan.example.test")
        assert scanner.scan.await_count == 2
        assert starts[1] - starts[0] >= 0.018
        assert report.target == "scan.example.test"
        assert report.resolved_ips == addresses
        assert [row.target for row in report.results["tcp"]] == list(addresses)
        assert report.to_dict()["resolved_ips"] == list(addresses)
        assert report.schema_version == 3

    asyncio.run(scenario())


def test_invalid_scope_or_ports_prevent_resolution_and_connections(monkeypatch):
    lookup = AsyncMock()
    monkeypatch.setattr("core.services.scanner_service.resolve_ipv4", lookup)
    for ports, scope in (([443], ["other.example.test"]), ([0], ["scan.example.test"])):
        with pytest.raises(ValueError):
            asyncio.run(
                ScannerService().run_all(
                    "scan.example.test", ports, allowed_targets=scope
                )
            )
    lookup.assert_not_awaited()


def test_dns_failure_prevents_tcp_probes(monkeypatch):
    scanner = TCPPortScanner()
    scanner.scan = AsyncMock()
    monkeypatch.setattr(
        dns.asyncresolver, "resolve", AsyncMock(side_effect=dns.resolver.NXDOMAIN())
    )
    with pytest.raises(TargetResolutionError):
        asyncio.run(
            ScannerService(scanner).run_all(
                "scan.example.test", [443], allowed_targets=["scan.example.test"]
            )
        )
    scanner.scan.assert_not_awaited()


def test_local_dns_cname_and_multiple_tcp_destinations(monkeypatch):
    async def scenario():
        class LocalDNS(asyncio.DatagramProtocol):
            def connection_made(self, transport):
                self.transport = transport
                self.queries = 0

            def datagram_received(self, data, address):
                query = dns.message.from_wire(data)
                self.queries += 1
                answer = dns.message.make_response(query)
                answer.answer.extend(
                    [
                        dns.rrset.from_text(
                            "scan.example.test.",
                            60,
                            "IN",
                            "CNAME",
                            "service.example.test.",
                        ),
                        dns.rrset.from_text(
                            "service.example.test.",
                            60,
                            "IN",
                            "A",
                            "127.0.0.1",
                            "127.0.0.2",
                        ),
                    ]
                )
                self.transport.sendto(answer.to_wire(), address)

        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            LocalDNS, local_addr=("127.0.0.1", 0)
        )
        resolver = dns.asyncresolver.Resolver(configure=False)
        resolver.nameservers = ["127.0.0.1"]
        resolver.port = transport.get_extra_info("sockname")[1]
        monkeypatch.setattr(dns.asyncresolver, "resolve", resolver.resolve)
        try:
            with socket.socket() as listener, socket.socket() as refused:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
                listener.listen()
                refused.bind(("127.0.0.2", port))
                report = await ScannerService().run_all(
                    "scan.example.test", [port], allowed_targets=["scan.example.test"]
                )
            assert protocol.queries == 1
            assert report.resolved_ips == ("127.0.0.1", "127.0.0.2")
            assert [(row.target, row.state) for row in report.results["tcp"]] == [
                ("127.0.0.1", PortState.OPEN),
                ("127.0.0.2", PortState.CLOSED),
            ]
        finally:
            transport.close()

    asyncio.run(scenario())
