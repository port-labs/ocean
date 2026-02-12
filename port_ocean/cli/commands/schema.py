# -*- coding: utf-8 -*-
"""CLI commands to extract JSON schemas."""

import copy
import json
import sys
from pathlib import Path
from typing import Any, Type

import click
import jsonref  # type: ignore[import-untyped]

from port_ocean.cli.commands.main import cli_start
from port_ocean.core.handlers import BasePortAppConfig
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.utils.misc import get_integration_class, get_spec_file


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


def _remove_orphaned_definitions(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove definitions that are no longer referenced anywhere in the schema."""
    definitions = schema.get("definitions")
    if not definitions:
        return schema

    ref_pattern = "#/definitions/"
    raw = json.dumps(schema)
    for name in list(definitions):
        if f'"{ref_pattern}{name}"' not in raw:
            del definitions[name]
            raw = json.dumps(schema)

    return schema


def _omit_loose_kind_definitions(schema: dict[str, Any]) -> dict[str, Any]:
    """Remove resource config variants whose ``kind`` accepts any string
    (i.e. not restricted by ``const`` or ``enum``), and clean up orphaned
    definitions left behind."""
    schema = copy.deepcopy(schema)
    resolved = jsonref.replace_refs(schema)

    items = schema.get("properties", {}).get("resources", {}).get("items", {})
    resolved_items = (
        resolved.get("properties", {}).get("resources", {}).get("items", {})
    )
    key = next((k for k in ("anyOf", "oneOf") if k in items), None)
    if not key:
        return schema

    items[key] = [
        v
        for v, rv in zip(items[key], resolved_items[key])
        if {"const", "enum"} & rv.get("properties", {}).get("kind", {}).keys()
    ]
    if len(items[key]) == 1:
        items.update(items.pop(key)[0])

    return _remove_orphaned_definitions(schema)


def _extract_integration_schema(path: str) -> dict[str, Any]:
    """
    Extract JSON schema for an integration.

    Args:
        path: Path to the integration directory

    Returns:
        JSON schema for the integration.
    """
    try:
        sys.path.append(path)
        integration_class = get_integration_class(path)
        if integration_class is None:
            click.echo(f"Integration class not found for {path}, omitting", err=True)
            return {}
        config_class = _get_config_class(integration_class)
        if config_class is None:
            config_class = PortAppConfig

        config_schema = config_class.schema()
        spec = get_spec_file(Path(path))
        if spec and not spec.get("customKindsEnabled", False):
            return _omit_loose_kind_definitions(config_schema)
        return config_schema
    except Exception as e:
        click.echo(f"Failed to extract schema from {path}: {e}", err=True)
        sys.exit(1)
    finally:
        sys.path.remove(path)


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
