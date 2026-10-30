"""Command-line interface for the network scanning service."""

import asyncio
import re
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from engine.services import ScannerService
from engine.services.tcp import PortState, TCPPortScanner

app = typer.Typer(help="Run Kowalski network scanners.")


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
    target: Annotated[str, typer.Argument(help="Literal IPv4 address to scan.")],
    ports: Annotated[
        str, typer.Option("--ports", help="Ports and ranges, e.g. 22,80,8000-8010.")
    ],
    allowed_targets: Annotated[
        list[str],
        typer.Option("--allow-ip", help="Authorized IPv4 address; repeat to add more."),
    ],
    timeout: Annotated[
        float, typer.Option(help="Connection timeout in seconds.")
    ] = 1.0,
    concurrency: Annotated[int, typer.Option(help="Maximum concurrent workers.")] = 20,
    rate_limit: Annotated[
        float, typer.Option(help="Maximum connection starts per second.")
    ] = 100.0,
    no_color: Annotated[
        bool, typer.Option("--no-color", help="Disable colored output.")
    ] = False,
) -> None:
    """Scan selected TCP ports within an explicitly authorized IPv4 scope."""
    selected_ports = parse_ports(ports)
    try:
        scanner = TCPPortScanner(
            timeout=timeout, concurrency=concurrency, rate_limit=rate_limit
        )
        results = asyncio.run(
            ScannerService(tcp_scanner=scanner).run_all(
                target, selected_ports, allowed_targets=allowed_targets
            )
        )
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    except KeyboardInterrupt:
        Console(stderr=True, no_color=no_color).print("Scan cancelled.")
        raise typer.Exit(code=130) from None

    console = Console(no_color=no_color)
    colors = {
        PortState.OPEN: "green",
        PortState.CLOSED: "red",
        PortState.UNKNOWN: "yellow",
    }
    for scanner_name, port_results in results.items():
        table = Table(title=Text(f"Kowalski · {scanner_name.upper()} · {target}"))
        table.add_column("Port", justify="right")
        table.add_column("State")
        table.add_column("Evidence")
        for result in port_results:
            table.add_row(
                str(result.port),
                Text(result.state.value, style=colors[result.state]),
                Text(result.evidence),
            )
        console.print(table)
        console.print(f"Scanned {len(port_results)} ports.")


if __name__ == "__main__":
    app()
