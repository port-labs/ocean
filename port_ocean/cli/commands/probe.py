import re

import click

from port_ocean.cli.commands.main import cli_start, console
from port_ocean.config.settings import LogLevelType
from port_ocean.core.probe import ProbeMode
from port_ocean.run import run_probe


def _parse_kinds(
    _ctx: click.Context, _param: click.Parameter, value: str | None
) -> list[str] | None:
    if value is None:
        return None
    kinds = [kind.strip() for kind in re.split(r"[\s,]+", value) if kind.strip()]
    if not kinds:
        raise click.BadParameter("must contain at least one kind")
    return kinds


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
@click.option(
    "--mode",
    type=click.Choice([mode.value for mode in ProbeMode], case_sensitive=False),
    default=ProbeMode.SHALLOW.value,
    show_default=True,
    help="Probe mode to run.",
)
@click.option(
    "--kinds",
    callback=_parse_kinds,
    help="""Comma- or space-separated list of resource kinds to probe
            (e.g. `--kinds repository,pull-request` or `--kinds repository pull-request`).
            If omitted, all kinds from the integration spec are probed.""",
)
def probe(
    path: str,
    probe_id: str | None,
    log_level: LogLevelType,
    mode: str,
    kinds: list[str] | None,
) -> None:
    """Run an integration's connection probe and exit."""
    try:
        run_probe(
            probe_id,
            path,
            log_level,
            kinds=kinds,
            mode=ProbeMode(mode),
        )
    except Exception as error:
        raise click.ClickException(f"Probe failed: {error}") from error

    console.print("Probe succeeded")
