# -*- coding: utf-8 -*-

import click

from port_ocean import __version__
from port_ocean.cli.commands.main import cli_start, console


@cli_start.command()
@click.option(
    "-s",
    "--short",
    "short",
    default=False,
    is_flag=True,
    required=False,
    help="Display only the short version number.",
)
def version(short: bool) -> None:
    """
    Displays the version of the Ocean package.
    """
    if short:
        console.print(__version__)
    else:
        console.print(f"🌊 Ocean version: {__version__}")
