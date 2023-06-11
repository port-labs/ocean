# -*- coding: utf-8 -*-

import click
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
    print_logo()


@cli_start.command()
@click.argument("path", default=".")
def sail(path: str) -> None:
    from port_ocean.port_ocean import run

    print("Setting sail... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓️")
    run(path)


@cli_start.command()
def new() -> None:
    print("⚓️ Docking at at Port... Initializing you integration.")
    print("🌟 Integration initialized successfully! Happy Porting!")


if __name__ == "__main__":
    cli_start()
