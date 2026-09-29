#!/usr/bin/env python
"""CLI for smoke config discovery and shell env export."""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import sys

from port_ocean.tests.smoke.config_registry import (
    list_config_names,
    load_config,
    ocean_config_env,
)

HOST_PORT = 18080


def _export_shell(config_name: str) -> str:
    config = load_config(config_name)
    ocean_env = ocean_config_env(config.ocean)
    lines = [
        f"export SMOKE_TEST_CONFIG={shlex.quote(config_name)}",
        f"export SMOKE_TEST_HOST_PORT={HOST_PORT}",
        f"export SMOKE_TEST_CONFIG_SUFFIX={shlex.quote(config_name)}",
        f"export SMOKE_TEST_LIFECYCLE={shlex.quote(config.lifecycle)}",
        f"export SMOKE_TEST_WAIT_FOR_RESYNC={shlex.quote('true' if config.wait_for_resync else 'false')}",
        f"export SMOKE_OCEAN_ENV_KEYS={shlex.quote(' '.join(ocean_env))}",
    ]
    for key, value in ocean_env.items():
        lines.append(f"export {key}={shlex.quote(value)}")
    return "\n".join(lines)


def _wait_for_resync() -> None:
    from port_ocean.tests.smoke.helpers.port_client import wait_for_resync_completed

    asyncio.run(wait_for_resync_completed())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke config utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available config names")
    subparsers.add_parser(
        "wait-resync", help="Block until the current config resync completes"
    )

    export_parser = subparsers.add_parser("export", help="Export config as shell env")
    export_parser.add_argument("config")

    describe_parser = subparsers.add_parser("describe", help="Print config as JSON")
    describe_parser.add_argument("config")

    args = parser.parse_args(argv)

    if args.command == "list":
        for name in list_config_names():
            print(name)
        return 0

    if args.command == "wait-resync":
        _wait_for_resync()
        return 0

    config = load_config(args.config)

    if args.command == "export":
        print(_export_shell(args.config))
        return 0

    if args.command == "describe":
        print(
            json.dumps(
                {
                    "name": config.name,
                    "lifecycle": config.lifecycle,
                    "wait_for_resync": config.wait_for_resync,
                    "ocean": config.ocean,
                    "env": ocean_config_env(config.ocean),
                },
                indent=2,
            )
        )
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
