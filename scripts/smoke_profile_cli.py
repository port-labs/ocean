#!/usr/bin/env python
"""CLI for smoke profile discovery and shell env export."""

from __future__ import annotations

import argparse
import json
import sys

from port_ocean.tests.smoke.profile_registry import (
    integration_config_env_key,
    list_profile_names,
    load_profile,
)


def _export_shell(profile_name: str) -> str:
    profile = load_profile(profile_name)
    lines = [
        f'export SMOKE_TEST_PROFILE="{profile_name}"',
        f'export SMOKE_TEST_RESOURCE_KINDS="{",".join(profile.resource_kinds)}"',
        f'export SMOKE_TEST_HOST_PORT="{profile.host_port}"',
        f'export SMOKE_TEST_PROFILE_SUFFIX="{profile.profile_suffix}"',
        f'export SMOKE_TEST_PROFILE_MODE="{profile.mode}"',
    ]
    for key, value in profile.integration_config.items():
        lines.append(f'export {integration_config_env_key(key)}="{value}"')
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke profile utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available profile names")

    export_parser = subparsers.add_parser("export", help="Export profile as shell env")
    export_parser.add_argument("profile")

    mode_parser = subparsers.add_parser("mode", help="Print profile integration mode")
    mode_parser.add_argument("profile")

    describe_parser = subparsers.add_parser("describe", help="Print profile as JSON")
    describe_parser.add_argument("profile")

    args = parser.parse_args(argv)

    if args.command == "list":
        for name in list_profile_names():
            print(name)
        return 0

    profile = load_profile(args.profile)

    if args.command == "export":
        print(_export_shell(args.profile))
        return 0

    if args.command == "mode":
        print(profile.mode)
        return 0

    if args.command == "describe":
        payload = {
            "name": profile.name,
            "mode": profile.mode,
            "profile_suffix": profile.profile_suffix,
            "resource_kinds": list(profile.resource_kinds),
            "host_port": profile.host_port,
            "integration": profile.integration_config,
        }
        print(json.dumps(payload, indent=2))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
