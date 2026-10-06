#!/usr/bin/env python3
"""CLI entry point for post-merge release application."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CI_DIR))

from ocean_release.applier import apply  # noqa: E402
from ocean_release.git_context import GitContext  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply Ocean release intent after merge"
    )
    parser.add_argument(
        "--merge-sha", required=True, help="Merge commit SHA to process"
    )
    parser.add_argument(
        "--main-ref", default="origin/main", help="Current main ref for version base"
    )
    parser.add_argument(
        "--skip-commit", action="store_true", help="Apply files but do not commit"
    )
    parser.add_argument(
        "--skip-checkout",
        action="store_true",
        help="Apply on the current branch without detaching to merge-sha",
    )
    args = parser.parse_args()

    git = GitContext(REPO_ROOT)
    if not args.skip_checkout:
        git.checkout_detach(args.merge_sha, fetch_ref=args.main_ref)

    applied = apply(git, merge_sha=args.merge_sha, main_ref=args.main_ref)

    if not applied:
        print("No releases to apply")
        return 0

    if not args.skip_commit:
        labels = ", ".join(release.target.label for release in applied)
        git.commit_all(f"chore: apply ocean releases for {labels} [ocean-release]")

    print(json.dumps([release.to_dict() for release in applied], indent=2))

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        subprocess.CalledProcessError,
        OSError,
        ValueError,
        FileNotFoundError,
    ) as exc:
        print(f"apply_ocean_release failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
