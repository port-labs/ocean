#!/usr/bin/env python3
"""CLI entry point for integration port_ocean pin validation."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parents[1]
CI_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(CI_DIR))

from ocean_release.git_context import GitContext  # noqa: E402
from ocean_release.ocean_dependency import validate_ocean_dependency_bumps  # noqa: E402


def main() -> int:
    errors = validate_ocean_dependency_bumps(GitContext(REPO_ROOT))

    if not errors:
        print("Ocean dependency validation passed")
        return 0

    print("Ocean dependency validation failed:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
