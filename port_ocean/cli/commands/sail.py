# -*- coding: utf-8 -*-

import click
import os

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
    is_flag=True,
    help="""Set to true to create default resources on installation.
            If not specified, the default value is false.""",
)
@click.option(
    "-O",
    "--once",
    "once",
    type=bool,
    is_flag=True,
    help="""specify the option to run the integration once and exit.""",
)
@click.option(
    "-d",
    "--docker",
    "docker",
    type=bool,
    is_flag=True,
    help="""specify the option to run the integration in a docker container.""",
)
@click.option(
    "-I",
    "--integration",
    "integration",
    type=str,
    help="""specify the integration to sail with, required only when using docker flag.""",
)
@click.option(
    "-v",
    "--version",
    "version",
    type=str,
    help="""specify the version of the integration to sail with.
            If not specified, the latest version will be used. Required only when using docker flag""",
)
def sail(
    path: str,
    log_level: LogLevelType,
    port: int,
    initialize_port_resources: bool | None,
    once: bool,
    docker: bool,
    integration: str,
    version: str,
) -> None:
    """
    Runs the integration in the given PATH. if no PATH is provided, the current directory will be used.

    PATH: Path to the integration.
    """
    if once and docker:
        from port_ocean.cli.commands.dockerized import run_once

        if not integration:
            console.print("integration is required when using --docker flag.")
            return
        if not version:
            console.print("version is not specified, using latest version.")
            version = "latest"

        console.print(
            "Sailing away, starting docking... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓️"
        )
        run_once(integration, version)
    else:
        from port_ocean import run

        print_logo()

        console.print("Setting sail... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓️")

        if once:
            os.environ["OCEAN__EVENT_LISTENER"] = '{"type": "IMMEDIATE"}'

        if docker:
            console.print("docker flag is not supported not when using --once flag.")
            return
        run(path, log_level, port, initialize_port_resources)
