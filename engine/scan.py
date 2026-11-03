"""Command-line interface for the network scanning service."""

import asyncio
import re
from enum import StrEnum
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from engine.services import ScannerService
from engine.services.tcp import PortState, TCPPortScanner

app = typer.Typer(help="Run Kowalski network scanners.")


class OutputFormat(StrEnum):
    TABLE = "table"
    JSON = "json"


def parse_ports(value: str) -> list[int]:
    """Parse comma-separated ports and inclusive ranges without network I/O."""
    ports: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not re.fullmatch(r"[0-9]+(?:-[0-9]+)?", item):
            raise typer.BadParameter(
                "Use ports or ranges, for example 22,80,8000-8010.",
                param_hint="--ports",
            )
        bounds = item.split("-")
        start = int(bounds[0])
        end = int(bounds[-1])
        if not 1 <= start <= end <= 65535:
            raise typer.BadParameter(
                "Ports must be between 1 and 65535; ranges must ascend.",
                param_hint="--ports",
            )
        ports.update(range(start, end + 1))
    return sorted(ports)


@app.command()
def scan(
    target: Annotated[str, typer.Argument(help="IPv4 address or hostname to scan.")],
    ports: Annotated[
        str, typer.Option("--ports", help="Ports and ranges, e.g. 22,80,8000-8010.")
    ],
    allowed_targets: Annotated[
        list[str],
        typer.Option(
            "--allow-target",
            "--allow-ip",
            help="Authorized IPv4 address or hostname; repeat to add more.",
        ),
    ],
    timeout: Annotated[
        float, typer.Option(help="Connection timeout in seconds.")
    ] = 1.0,
    concurrency: Annotated[int, typer.Option(help="Maximum concurrent workers.")] = 20,
    rate_limit: Annotated[
        float, typer.Option(help="Maximum connection starts per second.")
    ] = 100.0,
    output_format: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.TABLE,
    service_ports: Annotated[
        str,
        typer.Option(
            "--service-ports", help="SSH identification ports; use none to disable."
        ),
    ] = "22",
    no_color: Annotated[
        bool, typer.Option("--no-color", help="Disable colored output.")
    ] = False,
) -> None:
    """Scan selected TCP ports on an authorized IPv4 address or hostname."""
    selected_ports = parse_ports(ports)
    identification_ports = [] if service_ports == "none" else parse_ports(service_ports)
    try:
        scanner = TCPPortScanner(
            timeout=timeout, concurrency=concurrency, rate_limit=rate_limit
        )
        report = asyncio.run(
            ScannerService(tcp_scanner=scanner).run_all(
                target,
                selected_ports,
                allowed_targets=allowed_targets,
                service_ports=identification_ports,
            )
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    except KeyboardInterrupt:
        Console(stderr=True, no_color=no_color).print("Scan cancelled.")
        raise typer.Exit(code=130) from None

    console = Console(no_color=no_color)
    if output_format == OutputFormat.JSON:
        typer.echo(report.to_json())
        return
    colors = {
        PortState.OPEN: "green",
        PortState.CLOSED: "red",
        PortState.UNKNOWN: "yellow",
    }
    for scanner_name, port_results in report.results.items():
        table = Table(
            title=Text(f"Kowalski · {scanner_name.upper()} · {report.target}")
        )
        table.add_column("Port", justify="right")
        table.add_column("IP address")
        table.add_column("State")
        table.add_column("Evidence")
        for result in port_results:
            table.add_row(
                str(result.port),
                Text(result.target),
                Text(result.state.value, style=colors[result.state]),
                Text(result.evidence),
            )
        console.print(table)
        console.print(f"{scanner_name.upper()} checks: {len(port_results)}")

    if report.services:
        table = Table(title="Service identification (advertised evidence)")
        for column in (
            "IP address",
            "Port",
            "Status",
            "Protocol",
            "Advertised software",
            "Error",
        ):
            table.add_column(column)
        for row in report.services:
            table.add_row(
                Text(row.ip_address),
                str(row.port),
                Text(row.status),
                Text(row.protocol or "unknown"),
                Text(row.advertised_software or ""),
                Text(row.error or ""),
            )
        console.print(table)


if __name__ == "__main__":
    app()
