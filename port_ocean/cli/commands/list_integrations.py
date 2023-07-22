# -*- coding: utf-8 -*-

from port_ocean.cli.commands.main import cli_start, console
from port_ocean.cli.list_integrations import list_git_folders


@cli_start.command(name="list")
def list_integrations() -> None:
    """
    List all available public integrations.
    """
    console.print("🌊 Here are the integrations available to you:", style="bold")
    options = list_git_folders("port-labs", "port-ocean", "integrations")

    for option in options:
        console.print(f"⚓️ [bold][blue]{option}[/blue][/bold]")
