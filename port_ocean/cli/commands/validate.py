from __future__ import annotations

from pathlib import Path

import click

from port_ocean.cli.commands.main import cli_start, console
from port_ocean.validation.runner.errors import (
    ValidationExitCode,
    ValidationFailedError,
    ValidationSetupError,
)
from port_ocean.validation.runner.runner import ValidateOptions, run_validate


def _parse_scenarios(
    _ctx: click.Context, _param: click.Parameter, value: tuple[str, ...]
) -> list[str] | None:
    if not value:
        return None
    return list(value)


@cli_start.command()
@click.argument("path", default=".", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--scenario",
    "scenario_names",
    multiple=True,
    callback=_parse_scenarios,
    help="Run only the named scenario(s). May be passed multiple times.",
)
@click.option(
    "--update-expected",
    is_flag=True,
    default=False,
    help="Write actual Port entities to expected/ when diffs are intended.",
)
@click.option(
    "--keep",
    is_flag=True,
    default=False,
    help="Leave Port resources from the run in place (skip cleanup).",
)
@click.option(
    "--report",
    "report_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write a machine-readable JSON report to this file.",
)
def validate(
    path: str,
    scenario_names: list[str] | None,
    update_expected: bool,
    keep: bool,
    report_path: Path | None,
) -> None:
    """Validate an integration using local fixtures and the developer's Port org."""
    try:
        result = run_validate(
            ValidateOptions(
                integration_path=Path(path),
                scenario_names=scenario_names,
                update_expected=update_expected,
                keep=keep,
                report_path=report_path,
            )
        )
    except ValidationSetupError as error:
        console.print(f"[red]Setup error:[/red] {error.message}")
        raise SystemExit(ValidationExitCode.SETUP_ERROR) from error
    except ValidationFailedError as error:
        console.print(f"[red]Validation failed:[/red] {error.message}")
        raise SystemExit(ValidationExitCode.VALIDATION_FAILED) from error

    integration_name = result.paths.integration_name
    console.print(
        f"Loaded {len(result.scenario_names)} scenario(s) for [bold]{integration_name}[/bold]."
    )
    for name in result.scenario_names:
        kinds = result.scenarios.scenarios[name].kinds
        kinds_label = ", ".join(kinds) if kinds else "all configured kinds"
        console.print(f"  • {name} ({kinds_label})")

    # RUN-1 ends here; scenario execution is added in upcoming runner PRs.
    console.print(
        "[yellow]Scenario execution is not implemented yet; "
        "preflight checks passed.[/yellow]"
    )
