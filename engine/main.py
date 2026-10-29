"""Try the CLI presentation with simulated results; no network requests are made."""

from time import sleep
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

app = typer.Typer(help="Kowalski terminal output demo.")


@app.command()
def main(
    no_color: Annotated[
        bool, typer.Option("--no-color", help="Disable colored output.")
    ] = False,
) -> None:
    """Display a progress bar and a table of simulated TCP results."""
    console = Console(no_color=no_color)
    console.print("[bold cyan]Kowalski[/bold cyan] · CLI demo")
    console.print("Simulated results — no network connections are made.\n")

    table = Table(title="Demo TCP results")
    table.add_column("Port", justify="right")
    table.add_column("State")
    table.add_column("Evidence")

    results = [
        (8000, "open", "green", "Connection accepted"),
        (8001, "closed", "red", "Connection refused"),
        (8002, "unknown", "yellow", "Connection timeout"),
    ]
    for port, state, color, evidence in track(
        results,
        description="Preparing demo...",
        console=console,
        disable=not console.is_terminal,
    ):
        sleep(0.15)
        table.add_row(str(port), f"[{color}]{state}[/{color}]", evidence)

    console.print(table)


if __name__ == "__main__":
    app()
