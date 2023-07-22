import click

from port_ocean.cli.commands.main import cli_start
from port_ocean.cli.download_git_folder import download_github_folder


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
