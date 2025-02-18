# -*- coding: utf-8 -*-
from inspect import getmembers

import click

from port_ocean.bootstrap import create_default_app
from port_ocean.cli.commands.main import print_logo, console
from port_ocean.core.defaults import clean_defaults
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import load_module
from port_ocean.utils.signal import init_signal_handler
from .group import defaults


@defaults.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "-f",
    "--force",
    "force",
    is_flag=True,
    help="Delete all the entities of the Blueprint as well as the blueprint itself.",
)
@click.option(
    "-w",
    "--wait",
    "wait",
    is_flag=True,
    help="Wait for the migration to finish. when force is set to true.",
)
@click.option(
    "-d",
    "--destroy",
    "destroy",
    is_flag=True,
    help="Destroy the integration after cleaning the defaults.",
)
def clean(path: str, force: bool, wait: bool, destroy: bool) -> None:
    """
    Clean defaults of the integration from the .port/resources PATH.

    PATH: Path to the integration. If not provided, the current directory will be used.
    """
    init_signal_handler()
    print_logo()

    console.print("Cleaning blueprints and configurations! ⚓️")

    if force:
        console.print(
            "Deleting entities forcefully I sure hope you know what you are doing 🚨 🚨 🚨 ",
        )
    default_app = create_default_app(path)

    main_path = f"{path}/main.py" if path else "main.py"

    app_module = load_module(main_path)
    app: Ocean = {name: item for name, item in getmembers(app_module)}.get(
        "app",
        default_app,
    )

    clean_defaults(
        app.integration.AppConfigHandlerClass.CONFIG_CLASS,
        app.config,
        force,
        wait,
        destroy,
    )
