# -*- coding: utf-8 -*-
# ruff: noqa: E501
import os

import click
from cookiecutter.main import cookiecutter  # type: ignore
from rich.console import Console

from port_ocean import __version__
from port_ocean.cli.download_git_folder import download_github_folder
from port_ocean.cli.list_integrations import list_git_folders
from port_ocean.config.integration import LogLevelType

console = Console()


def print_logo() -> None:
    ascii_art = """
=====================================================================================
          ::::::::       ::::::::       ::::::::::           :::        ::::    ::: 
        :+:    :+:     :+:    :+:      :+:                :+: :+:      :+:+:   :+:  
       +:+    +:+     +:+             +:+               +:+   +:+     :+:+:+  +:+   
      +#+    +:+     +#+             +#++:++#         +#++:++#++:    +#+ +:+ +#+    
     +#+    +#+     +#+             +#+              +#+     +#+    +#+  +#+#+#     
    #+#    #+#     #+#    #+#      #+#              #+#     #+#    #+#   #+#+#      
    ########       ########       ##########       ###     ###    ###    ####      
=====================================================================================
By: Port.io
"""

    # Display ASCII art
    Console().print(ascii_art.strip())


@click.group
def cli_start() -> None:
    # Ocean root command
    pass


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


@cli_start.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def new(path: str) -> None:
    """
    Scaffold a new integration in the given PATH.

    PATH: Path to the integration. If not provided, the current directory will be used.
    """
    print_logo()

    console.print(
        "🚢 Unloading cargo... Setting up your integration at the dock.", style="bold"
    )

    result = cookiecutter(f"{os.path.dirname(__file__)}/cookiecutter", output_dir=path)
    name = result.split("/")[-1]

    console.print(
        "\n🌊 Ahoy, Captain! Your project is ready to set sail into the vast ocean of possibilities!",
        style="bold",
    )
    console.print("Here are your next steps:\n", style="bold")
    console.print(
        "⚓️ Install necessary packages: Run [bold][blue]make install[/blue][/bold] to install all required packages for your project.\n"
        f"▶️ [bold][blue]cd {path}/{name} && make install && . .venv/bin/activate[/blue][/bold]\n"
    )
    console.print(
        "⚓️ Set sail with [blue]Ocean[/blue]: Run [bold][blue]ocean sail[/blue] <path_to_integration>[/bold] to run the project using Ocean.\n"
        f"▶️ [bold][blue]ocean sail {path}/{name}[/blue][/bold] \n"
    )
    console.print(
        "⚓️ Smooth sailing with [blue]Make[/blue]: Alternatively, you can run [bold][blue]make run[/blue][/bold] to launch your project using Make. \n"
        f"▶️ [bold][blue]make run {path}/{name}[/blue][/bold]"
    )


@cli_start.command(name="list")
def list_integrations() -> None:
    """
    List all available public integrations.
    """
    console.print("🌊 Here are the integrations available to you:", style="bold")
    options = list_git_folders("port-labs", "port-ocean", "integrations")

    for option in options:
        console.print(f"⚓️ [bold][blue]{option}[/blue][/bold]")


@cli_start.command()
@click.argument("name", type=str)
@click.option(
    "-p",
    "--path",
    "path",
    default=None,
    type=click.Path(exists=True),
    help="Desired path to pull the integration to. defaults to ./NAME",
)
def pull(name: str, path: str) -> None:
    """
    Pull an integration bt the NAME from the list of available public integrations.

    NAME: Name of the integration to pull.
    """
    download_github_folder(
        "port-labs", "Port-Ocean", f"integrations/{name}", path or f"./{name}"
    )
