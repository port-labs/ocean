# -*- coding: utf-8 -*-
"""CLI commands to extract JSON schemas."""

import json
import sys
from pathlib import Path
from typing import Any, Type

import click

from port_ocean.cli.commands.main import cli_start
from port_ocean.core.handlers import BasePortAppConfig
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.utils.misc import get_integration_class


@cli_start.group()
def schema() -> None:
    """Extract JSON schemas for integrations."""
    pass


def _get_config_class(
    integration_class: Type[BaseIntegration],
) -> Type[PortAppConfig]:
    """Extract CONFIG_CLASS from the integration's AppConfigHandlerClass."""
    handler_class: Type[BasePortAppConfig] = integration_class.AppConfigHandlerClass
    return handler_class.CONFIG_CLASS


def _extract_integration_schema(path: str) -> dict[str, Any]:
    """
    Extract JSON schema for an integration.

    Args:
        path: Path to the integration directory

    Returns:
        JSON schema for the integration.
    """
    try:
        integration_class = get_integration_class(path)
        config_class = _get_config_class(integration_class)
        if config_class is None:
            config_class = PortAppConfig

        return config_class.schema()
    except ModuleNotFoundError as e:
        click.echo(
            f"Failed to extract schema from {path}: {e}. "
            "Make sure the integration's dependencies are installed "
            "(run 'make install' or 'pip install -e .' in the integration directory).",
            err=True,
        )
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to extract schema from {path}: {e}", err=True)
        sys.exit(1)


@schema.command("port-app-config")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    "output_file",
    default=None,
    type=click.Path(),
    help="Output file path. If not specified, prints to stdout.",
)
@click.option(
    "--pretty/--compact",
    "pretty",
    default=True,
    help="Pretty print JSON output (default: pretty).",
)
def port_app_config(path: str, output_file: str | None, pretty: bool) -> None:
    """
    Extract PortAppConfig JSON schema for an integration.

    PATH: Path to the integration directory (default: current directory).
    """
    result = _extract_integration_schema(path)

    indent = 2 if pretty else None
    json_output = json.dumps(result, indent=indent)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output)
        click.echo(
            click.style(
                f"Schema written to {output_file}",
                fg="green",
            ),
            err=True,
        )
    else:
        print(json_output)
