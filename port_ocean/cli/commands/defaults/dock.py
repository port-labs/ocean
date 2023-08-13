# -*- coding: utf-8 -*-
import click

from inspect import getmembers
from .group import defaults
from port_ocean import __version__
from port_ocean.cli.commands.main import print_logo, console
from port_ocean.cli.utils import cli_root_path
from port_ocean.ocean import Ocean
from port_ocean.cli.defaults.port_defaults import initialize_defaults
from port_ocean.run import _create_default_app, _load_module


@defaults.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def dock(path: str) -> None:
    """
    Apply defaults of the integration from the .port/resources PATH.

    PATH: Path to the integration. If not provided, the current directory will be used.
    """
    print_logo()

    console.print("Unloading cargo at the dock... 📦🚢")

    default_app = _create_default_app(path, False)

    main_path = f"{path}/main.py" if path else "main.py"

    app_module = _load_module(main_path)
    app: Ocean = {name: item for name, item in getmembers(app_module)}.get(
        "app",
        default_app,
    )

    initialize_defaults(
        app.integration.AppConfigHandlerClass.CONFIG_CLASS,
        app.config,
    )
