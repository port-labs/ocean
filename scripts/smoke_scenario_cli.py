#!/usr/bin/env python
"""CLI for smoke scenario discovery and shell env export."""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
import sys

from port_ocean.tests.smoke.scenario_registry import (
    list_scenario_names,
    load_scenario,
    ocean_config_env,
)


def _export_shell(scenario_name: str) -> str:
    scenario = load_scenario(scenario_name)
    ocean_env = ocean_config_env(scenario.ocean)
    lines = [
        f"export SMOKE_TEST_SCENARIO={shlex.quote(scenario_name)}",
        f"export SMOKE_TEST_RESOURCE_KINDS={shlex.quote(','.join(scenario.resource_kinds))}",
        f"export SMOKE_TEST_HOST_PORT={shlex.quote(str(scenario.host_port))}",
        f"export SMOKE_TEST_SCENARIO_SUFFIX={shlex.quote(scenario.suffix)}",
        f"export SMOKE_TEST_LIFECYCLE={shlex.quote(scenario.lifecycle)}",
        f"export SMOKE_TEST_PATHS={shlex.quote(' '.join(scenario.tests))}",
        f"export SMOKE_TEST_WAIT_FOR_RESYNC={shlex.quote('true' if scenario.wait_for_resync else 'false')}",
        f"export SMOKE_OCEAN_ENV_KEYS={shlex.quote(' '.join(ocean_env))}",
    ]
    for key, value in ocean_env.items():
        lines.append(f"export {key}={shlex.quote(value)}")
    return "\n".join(lines)


def _wait_for_resync() -> None:
    from port_ocean.tests.smoke.helpers.port_client import wait_for_resync_completed

    asyncio.run(wait_for_resync_completed())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke scenario utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available scenario names")
    subparsers.add_parser(
        "wait-resync", help="Block until the current scenario resync completes"
    )

    export_parser = subparsers.add_parser("export", help="Export scenario as shell env")
    export_parser.add_argument("scenario")

    describe_parser = subparsers.add_parser("describe", help="Print scenario as JSON")
    describe_parser.add_argument("scenario")

    args = parser.parse_args(argv)

    if args.command == "list":
        for name in list_scenario_names():
            print(name)
        return 0

    if args.command == "wait-resync":
        _wait_for_resync()
        return 0

    scenario = load_scenario(args.scenario)

    if args.command == "export":
        print(_export_shell(args.scenario))
        return 0

    if args.command == "describe":
        payload = {
            "name": scenario.name,
            "lifecycle": scenario.lifecycle,
            "suffix": scenario.suffix,
            "resource_kinds": list(scenario.resource_kinds),
            "host_port": scenario.host_port,
            "tests": list(scenario.tests),
            "wait_for_resync": scenario.wait_for_resync,
            "ocean": scenario.ocean,
            "env": ocean_config_env(scenario.ocean),
        }
        print(json.dumps(payload, indent=2))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
