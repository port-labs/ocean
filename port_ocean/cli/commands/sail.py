# -*- coding: utf-8 -*-

import click

from port_ocean.cli.commands.main import cli_start, print_logo, console
from port_ocean.config.settings import LogLevelType


@cli_start.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "-l",
    "--log-level",
    "log_level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="DEBUG",
    help="""Set the logging level for the integration.
            Supported levels are DEBUG, INFO, WARNING, ERROR,
            and CRITICAL. If not specified, the default level
            is DEBUG.""",
)
@click.option(
    "-p",
    "--port",
    "port",
    type=int,
    default=8000,
    help="""Set the port for the integration to run on.
            If not specified, the default port is 8000.""",
)
@click.option(
    "-i",
    "--initialize-port-resources",
    "initialize_port_resources",
    type=bool,
    help="""Set to true to create default resources on installation.
            If not specified, the default value is false.""",
)
def sail(
    path: str,
    log_level: LogLevelType,
    port: int,
    initialize_port_resources: bool | None,
) -> None:
    """
    Runs the integration in the given PATH. if no PATH is provided, the current directory will be used.

    PATH: Path to the integration.
    """
    from port_ocean import run

    print_logo()

    console.print("Setting sail... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓️")
    run(path, log_level, port, initialize_port_resources)
