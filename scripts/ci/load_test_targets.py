#!/usr/bin/env python3
"""Discover and resolve integration load-test targets for post-merge CI."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedTargets:
    should_run: bool
    integration_arg: str
    targets_json: str


def discover_harness_integrations(
    repo_root: str | Path = "ocean-load-tests",
) -> list[str]:
    """Return integration names that have a load-test harness in ocean-load-tests.

    Discovery marker (same as ocean-load-tests/scripts/build_matrix.py):
      integrations/<name>/.env.load-test
    """
    integrations_dir = Path(repo_root) / "integrations"
    if not integrations_dir.is_dir():
        return []

    return sorted(
        marker.parent.name
        for marker in integrations_dir.glob("*/.env.load-test")
        if marker.is_file()
    )


def _parse_json_list(raw: str, env_name: str) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid {env_name}: {exc}") from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise SystemExit(f"{env_name} must be a JSON array of strings")
    return value


def _is_true(value: str | None) -> bool:
    return (value or "").lower() == "true"


def resolve_load_test_targets(
    *,
    changed_integrations: list[str],
    has_core_code_changes: bool,
    has_code_changes: bool,
    harness_integrations: list[str],
) -> ResolvedTargets:
    skip = ResolvedTargets(
        should_run=False,
        integration_arg="",
        targets_json="[]",
    )

    if not has_code_changes:
        print("No meaningful code changes — skipping load test.")
        return skip

    if has_core_code_changes:
        targets = list(harness_integrations)
        print(f"Core code changed — using full harness list: {targets}")
    else:
        harness_set = set(harness_integrations)
        targets = [name for name in changed_integrations if name in harness_set]
        print(f"Integration-scoped changes — targets: {targets}")

    if not targets:
        print("No changed integrations have a load-test harness — skipping.")
        return skip

    targets_json = json.dumps(targets, separators=(",", ":"))
    return ResolvedTargets(
        should_run=True,
        integration_arg=",".join(targets),
        targets_json=targets_json,
    )


def _write_github_output(path: Path, resolved: ResolvedTargets) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"should_run={'true' if resolved.should_run else 'false'}\n")
        handle.write(f"integration_arg={resolved.integration_arg}\n")
        handle.write(f"targets_json={resolved.targets_json}\n")


def main() -> int:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if not output_file:
        print("GITHUB_OUTPUT must be set", file=sys.stderr)
        return 1

    changed_integrations = _parse_json_list(
        os.environ.get("CHANGED_INTEGRATIONS_JSON", "[]"),
        "CHANGED_INTEGRATIONS_JSON",
    )
    has_core_code_changes = _is_true(os.environ.get("HAS_CORE_CODE_CHANGES"))
    has_code_changes = _is_true(os.environ.get("HAS_CODE_CHANGES"))

    override = os.environ.get("LOAD_TEST_INTEGRATIONS_JSON", "").strip()
    if override:
        harness_integrations = _parse_json_list(override, "LOAD_TEST_INTEGRATIONS_JSON")
    else:
        repo_root = os.environ.get("LOAD_TEST_REPO_ROOT", "ocean-load-tests")
        harness_integrations = discover_harness_integrations(repo_root)

    print(f"Load-test harness integrations: {harness_integrations}")

    resolved = resolve_load_test_targets(
        changed_integrations=changed_integrations,
        has_core_code_changes=has_core_code_changes,
        has_code_changes=has_code_changes,
        harness_integrations=harness_integrations,
    )
    _write_github_output(Path(output_file), resolved)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
