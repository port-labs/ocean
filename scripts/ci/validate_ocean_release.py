#!/usr/bin/env python3
"""CLI entry point for PR release validation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CI_DIR))

from ocean_release.git_context import GitContext  # noqa: E402
from ocean_release.validator import validate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Ocean release intent on a PR"
    )
    parser.add_argument("--base", default="origin/main", help="Base git ref")
    parser.add_argument("--head", default="HEAD", help="Head git ref")
    args = parser.parse_args()

    errors = validate(
        GitContext(REPO_ROOT),
        base_ref=args.base,
        head_ref=args.head,
    )

    if not errors:
        print("Release validation passed")
        return 0

    print("Release validation failed:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
