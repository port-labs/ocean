# -*- coding: utf-8 -*-

from inspect import getmembers
import os
import click
from cookiecutter.main import cookiecutter  # type: ignore

from port_ocean import __version__
from port_ocean.cli.commands.main import cli_start, print_logo, console
from port_ocean.cli.utils import cli_root_path
from port_ocean.ocean import Ocean
from port_ocean.port_defaults import clear_defaults as clear
from port_ocean.run import _create_default_app, _load_module


@cli_start.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "-f",
    "--force",
    "force",
    type=bool,
    default=False,
    help="Delete all the entities of the Blueprint as well as the blueprint itself.",
)
def clear_defaults(path: str, force: bool) -> None:
    """
    Apply defaults of the integration from the .port/resources PATH.

    PATH: Path to the integration. If not provided, the current directory will be used.
    """
    print_logo()

    console.print("Applying default blueprints and configurations! ⚓️")

    default_app = _create_default_app(path, False)

    main_path = f"{path}/main.py" if path else "main.py"

    app_module = _load_module(main_path)
    app: Ocean = {name: item for name, item in getmembers(app_module)}.get(
        "app",
        default_app,
    )

    clear(app.integration.AppConfigHandlerClass.CONFIG_CLASS, force)
