# -*- coding: utf-8 -*-
import click

from inspect import getmembers
from .group import defaults
from port_ocean.cli.commands.main import print_logo, console
from port_ocean.ocean import Ocean
from port_ocean.cli.defaults import clean_defaults
from port_ocean.run import _create_default_app, _load_module


@defaults.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "-f",
    "--force",
    "force",
    type=bool,
    default=False,
    help="Delete all the entities of the Blueprint as well as the blueprint itself.",
)
@click.option(
    "-w",
    "--wait",
    "wait",
    type=bool,
    default=False,
    help="Wait for the migration to finish. when force is set to true.",
)
def clean(path: str, force: bool, wait: bool) -> None:
    """
    Clean defaults of the integration from the .port/resources PATH.

    PATH: Path to the integration. If not provided, the current directory will be used.
    """
    print_logo()

    console.print("Cleaning blueprints and configurations! ⚓️")

    if force:
        console.print(
            "Deleting entities forcefully I sure hope you know what you are doing 🚨 🚨 🚨 ",
        )
    default_app = _create_default_app(path, False)

    main_path = f"{path}/main.py" if path else "main.py"

    app_module = _load_module(main_path)
    app: Ocean = {name: item for name, item in getmembers(app_module)}.get(
        "app",
        default_app,
    )

    clean_defaults(app.integration.AppConfigHandlerClass.CONFIG_CLASS, force, wait)
