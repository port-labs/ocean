import click

from port_ocean.cli.commands.main import cli_start, console
from port_ocean.config.settings import LogLevelType
from port_ocean.run import run_probe


@cli_start.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "--probe-id",
    default=None,
    envvar="OCEAN__PROBE_ID",
    help="""Identifier of the probe, assigned by the caller that requested it.
            Omit for a local run that does not report progress to Port.
            May also be provided via the `OCEAN__PROBE_ID` environment variable.""",
)
@click.option(
    "-l",
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Set the logging level for the probe.",
)
def probe(path: str, probe_id: str | None, log_level: LogLevelType) -> None:
    """Run an integration's connection probe and exit."""
    try:
        run_probe(probe_id, path, log_level)
    except Exception as error:
        raise click.ClickException(f"Probe failed: {error}") from error

    console.print("Probe succeeded")
