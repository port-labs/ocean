# -*- coding: utf-8 -*-
import os

import click
from cookiecutter.main import cookiecutter  # type: ignore
from rich import print
from rich.console import Console


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
    pass


@cli_start.command()
@click.argument("path", default=".")
def sail(path: str) -> None:
    from port_ocean.port_ocean import run

    print_logo()

    print("Setting sail... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓️")
    run(path)


@cli_start.command()
def new() -> None:
    print_logo()

    console = Console()
    console.print(
        "🚢 Unloading cargo... Setting up your integration at the port.", style="bold"
    )

    cookiecutter(f"{os.path.dirname(__file__)}/cookiecutter")

    console.print(
        "\n🌊 Ahoy, Captain! Your project has set sail into the vast ocean of possibilities!",
        style="bold",
    )
    console.print("Here are your next steps: \n", style="bold")
    console.print(
        "⚓️ Install necessary packages: Run [bold][blue]make install[/blue][/bold] to install all required packages for your project."
    )
    console.print(
        "⚓️ Set sail with [blue]Ocean[/blue]: Run [bold][blue]ocean sail[/blue] <path_to_integration>[/bold] to run the project using Ocean."
    )
    console.print(
        "⚓️ Smooth sailing with [blue]Make[/blue]: Alternatively, you can run [bold][blue]make run[/blue][/bold] to launch your project using Make. \n"
    )


if __name__ == "__main__":
    cli_start()
