# -*- coding: utf-8 -*-
from inspect import getmembers

import click

from port_ocean.bootstrap import create_default_app
from port_ocean.cli.commands.main import print_logo, console
from port_ocean.core.defaults.initialize import initialize_defaults
from port_ocean.ocean import Ocean
from port_ocean.utils.misc import load_module
from .group import defaults


@defaults.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def dock(path: str) -> None:
    """
    Apply defaults of the integration from the .port/resources PATH.

    PATH: Path to the integration. If not provided, the current directory will be used.
    """
    print_logo()

    console.print("Unloading cargo at the dock... 📦🚢")

    default_app = create_default_app(path)

    main_path = f"{path}/main.py" if path else "main.py"

    app_module = load_module(main_path)
    app: Ocean = {name: item for name, item in getmembers(app_module)}.get(
        "app",
        default_app,
    )

    initialize_defaults(
        app.integration.AppConfigHandlerClass.CONFIG_CLASS,
        app.config,
    )
