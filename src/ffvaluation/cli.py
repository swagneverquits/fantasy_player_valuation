from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ffvaluation.sources.registry import list_sources

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command()
def sources() -> None:
    """List candidate valuation sources."""

    table = Table(title="Candidate valuation sources")
    table.add_column("Source")
    table.add_column("Type")
    table.add_column("Access")
    table.add_column("Notes")

    for source in list_sources():
        table.add_row(
            source.name,
            source.valuation_type.value,
            source.access_method,
            source.notes or "",
        )

    console.print(table)

