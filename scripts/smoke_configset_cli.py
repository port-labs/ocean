#!/usr/bin/env python
"""CLI for smoke configset discovery and shell env export."""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import sys

from port_ocean.tests.smoke.configset_registry import (
    list_configset_names,
    load_configset,
    ocean_config_env,
)

HOST_PORT = 18080


def _export_shell(configset_name: str) -> str:
    configset = load_configset(configset_name)
    ocean_env = ocean_config_env(configset.ocean)
    lines = [
        f"export SMOKE_TEST_CONFIGSET={shlex.quote(configset_name)}",
        f"export SMOKE_TEST_HOST_PORT={HOST_PORT}",
        f"export SMOKE_TEST_CONFIGSET_SUFFIX={shlex.quote(configset_name)}",
        f"export SMOKE_TEST_WAIT_FOR_RESYNC={shlex.quote('true' if configset.wait_for_resync else 'false')}",
        f"export SMOKE_OCEAN_ENV_KEYS={shlex.quote(' '.join(ocean_env))}",
    ]
    for key, value in ocean_env.items():
        lines.append(f"export {key}={shlex.quote(value)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke configset utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available configset names")
    subparsers.add_parser(
        "wait-resync", help="Block until the current configset resync completes"
    )

    export_parser = subparsers.add_parser(
        "export", help="Export configset as shell env"
    )
    export_parser.add_argument("configset")

    describe_parser = subparsers.add_parser("describe", help="Print configset as JSON")
    describe_parser.add_argument("configset")

    args = parser.parse_args(argv)

    if args.command == "list":
        for name in list_configset_names():
            print(name)
        return 0

    if args.command == "wait-resync":
        # Lazy import: avoids pulling Port client deps on list/export/describe.
        from port_ocean.tests.smoke.helpers.port_client import wait_for_resync_completed

        asyncio.run(wait_for_resync_completed())
        return 0

    configset = load_configset(args.configset)

    if args.command == "export":
        print(_export_shell(args.configset))
        return 0

    if args.command == "describe":
        print(
            json.dumps(
                {
                    "name": configset.name,
                    "wait_for_resync": configset.wait_for_resync,
                    "ocean": configset.ocean,
                    "env": ocean_config_env(configset.ocean),
                },
                indent=2,
            )
        )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
