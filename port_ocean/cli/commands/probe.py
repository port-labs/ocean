import asyncio

import click

from port_ocean.bootstrap import load_ocean_app
from port_ocean.cli.commands.main import cli_start, console
from port_ocean.config.settings import ApplicationSettings, LogLevelType
from port_ocean.log.logger_setup import setup_logger
from port_ocean.utils.signal import init_signal_handler


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
    application_settings = ApplicationSettings(log_level=log_level)
    setup_logger(
        application_settings.log_level,
        enable_http_handler=application_settings.enable_http_logging,
    )

    init_signal_handler()
    app = load_ocean_app(path)
    try:
        asyncio.run(app.integration.run_probe())
    except Exception as error:
        raise click.ClickException(f"Probe failed: {error}") from error

    console.print("Probe succeeded")
