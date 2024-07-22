# -*- coding: utf-8 -*-

import click

from port_ocean import __version__, __integration_version__
from port_ocean.cli.commands.main import cli_start, print_logo, console
from port_ocean.config.settings import LogLevelType


@cli_start.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "-l",
    "--log-level",
    "log_level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="""Set the logging level for the integration.
            Supported levels are DEBUG, INFO, WARNING, ERROR,
            and CRITICAL. If not specified, the default level
            is INFO.""",
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
    help="""Set to False to not create default resources on installation.
            If not specified, will use the environment variable `OCEAN__INITIALIZE_PORT_RESOURCES` to determine whether 
            to initialize resources, and if not set, will default to True.""",
)
@click.option(
    "-O",
    "--once",
    "once",
    type=bool,
    is_flag=True,
    help="""specify the option to run the integration once and exit.""",
)
def sail(
    path: str,
    log_level: LogLevelType,
    port: int,
    initialize_port_resources: bool | None,
    once: bool,
) -> None:
    """
    Runs the integration in the given PATH. if no PATH is provided, the current directory will be used.

    PATH: Path to the integration.
    """
    from port_ocean import run

    print_logo()

    console.print("Setting sail... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓️")
    console.print(f"🌊 Ocean version: {__version__}")
    console.print(f"🚢 Integration version: {__integration_version__}")

    override = {}
    if once:
        console.print("Setting event listener to Once")
        override["event_listener"] = {"type": "ONCE"}

    run(
        path,
        log_level,
        port,
        initialize_port_resources=initialize_port_resources,
        config_override=override,
    )
