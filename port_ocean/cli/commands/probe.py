import click

from port_ocean.cli.commands.main import cli_start, console
from port_ocean.config.settings import LogLevelType
from port_ocean.run import run_probe


@cli_start.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "-l",
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Set the logging level for the probe.",
)
def probe(path: str, log_level: LogLevelType) -> None:
    """Run an integration's connection probe and exit."""
    try:
        run_probe(path, log_level)
    except Exception as error:
        raise click.ClickException(f"Probe failed: {error}") from error

    console.print("Probe succeeded")
