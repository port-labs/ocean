# -*- coding: utf-8 -*-
# ruff: noqa: E501

import os

import click
from cookiecutter.main import cookiecutter  # type: ignore
from rich import print
from rich.console import Console

from port_ocean.cli.download_git_folder import download_folder
from port_ocean.cli.list_integrations import list_git_folders


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
    Console().print(ascii_art)


@click.group()
def cli_start() -> None:
    # Ocean root command
    pass


@cli_start.command()
@click.argument("path", default="")
def sail(path: str) -> None:
    from port_ocean.port_ocean import run

    print_logo()

    print("Setting sail... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓️")
    run(path)


@cli_start.command()
@click.argument("path", default=".")
def new(path: str) -> None:
    print_logo()

    console = Console()
    console.print(
        "🚢 Unloading cargo... Setting up your integration at the port.", style="bold"
    )

    result = cookiecutter(f"{os.path.dirname(__file__)}/cookiecutter", output_dir=path)
    name = result.split("/")[-1]

    console.print(
        "\n🌊 Ahoy, Captain! Your project has set sail into the vast ocean of possibilities!",
        style="bold",
    )
    console.print("Here are your next steps: \n", style="bold")
    console.print(
        "⚓️ Install necessary packages: Run [bold][blue]make install[/blue][/bold] to install all required packages for your project.\n"
        f"▶️ [bold][blue]cd {path}/{name} && make install && . venv/bin/activate[/blue][/bold]\n"
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
    console = Console()
    console.print("🌊 Here are the integrations available to you:", style="bold")
    options = list_git_folders("https://github.com/port-labs/pulumi", "examples")

    for option in options:
        console.print(f"⚓️ [bold][blue]{option}[/blue][/bold]")


@cli_start.command()
@click.argument("name")
def pull(name: str) -> None:
    download_folder(
        "https://github.com/port-labs/pulumi", f"examples/{name}", f"./{name}"
    )
