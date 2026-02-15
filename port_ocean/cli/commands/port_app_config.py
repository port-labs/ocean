# -*- coding: utf-8 -*-
"""CLI commands for port-app-config"""

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


def _get_config_class(
    integration_class: Type[BaseIntegration],
) -> Type[PortAppConfig]:
    """Extract CONFIG_CLASS from the integration's AppConfigHandlerClass."""
    handler_class: Type[BasePortAppConfig] = integration_class.AppConfigHandlerClass
    return handler_class.CONFIG_CLASS


def _load_integration_class(path: str) -> Type[BaseIntegration]:
    """Load the integration class from *path*, handling errors."""
    try:
        sys.path.append(path)
        return get_integration_class(path)
    except FileNotFoundError:
        click.echo(f"Integration class not found for {path}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to load integration from {path}: {e}", err=True)
        sys.exit(1)


def _write_json_output(
    data: dict[str, Any],
    output_file: str | None,
    pretty: bool,
    label: str,
) -> None:
    """Serialise *data* as JSON to *output_file* or stdout."""
    indent = 2 if pretty else None
    json_output = json.dumps(data, indent=indent)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_output)
        click.echo(
            click.style(f"{label} written to {output_file}", fg="green"),
            err=True,
        )
    else:
        print(json_output)


@cli_start.group("port-app-config")
def port_app_config() -> None:
    """Commands related to port-app-config"""
    pass


@port_app_config.command("schema")
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
def port_app_config_schema(
    path: str,
    output_file: str | None,
    pretty: bool,
) -> None:
    """
    Extract the PortAppConfig JSON schema for an integration.

    PATH: Path to the integration directory (default: current directory).
    """
    try:
        integration_class = _load_integration_class(path)
        config_class = _get_config_class(integration_class)
        config_class.validate_and_get_resource_kinds(
            integration_class.allow_custom_kinds
        )
        result = config_class.schema()
    finally:
        sys.path.remove(path)

    _write_json_output(result, output_file, pretty, label="Schema")


@port_app_config.command("list-kinds")
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
def port_app_config_list_kinds(
    path: str,
    output_file: str | None,
    pretty: bool,
) -> None:
    """
    List the resource kinds defined by an integration.

    PATH: Path to the integration directory (default: current directory).
    """
    integration_class = _load_integration_class(path)
    try:
        result = _get_config_class(integration_class).validate_and_get_resource_kinds(
            integration_class.allow_custom_kinds
        )
    finally:
        sys.path.remove(path)

    _write_json_output(result, output_file, pretty, label="Kinds")
