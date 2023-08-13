# -*- coding: utf-8 -*-
import click

from inspect import getmembers
from .group import defaults
from port_ocean import __version__
from port_ocean.cli.commands.main import print_logo, console
from port_ocean.cli.utils import cli_root_path
from port_ocean.ocean import Ocean
from port_ocean.cli.defaults.port_defaults import clean_defaults
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
def clean(path: str, force: bool) -> None:
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

    migration_ids = clean_defaults(
        app.integration.AppConfigHandlerClass.CONFIG_CLASS, force
    )

    if (
        migration_ids
        and len([migration_id for migration_id in migration_ids if migration_id]) > 0
    ):
        console.print(
            f"The clean migration has started, you can track the migration process using the following migration ids {migration_ids} ⚓️"
        )
