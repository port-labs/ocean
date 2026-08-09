"""Validates PRs for manual or declarative version releases."""

from __future__ import annotations

from pathlib import Path

from .git_context import GitContext
from .models import ReleaseTarget
from .release_file import parse_release_file, target_from_release_path
from .version import (
    parse_version,
    validate_target_version_label,
)


def validate(git: GitContext, *, base_ref: str, head_ref: str) -> list[str]:
    errors: list[str] = []
    release_files_by_target = _release_files_by_target(git, base_ref, head_ref)
    targets = git.changed_release_targets(base_ref, head_ref)

    print(f"Validating {len(targets)} release target(s) ({base_ref}...{head_ref})")
    if release_files_by_target:
        for (kind, name), files in release_files_by_target.items():
            print(f"  Found release file(s) for {kind}/{name}: {len(files)}")

    for target in targets:
        print(f"Checking {target.label}")
        release_files = release_files_by_target.get((target.kind, target.name), [])
        if release_files:
            print(f"  {target.label}: validating declarative release")
            errors.extend(_validate_declarative(git, target, release_files))
            continue

        version_changed = git.has_version_changed(
            base_ref, head_ref, target.pyproject_path
        )
        changelog_changed = git.has_changelog_changed(
            base_ref, head_ref, target.changelog_path
        )

        if version_changed and changelog_changed:
            print(f"  {target.label}: validating manual release")
            errors.extend(_validate_manual_version(git, target))
            continue

        if version_changed or changelog_changed:
            print(f"  {target.label}: partial manual release detected")
            errors.append(
                f"{target.label}: partial manual release — bump both version and changelog, "
                "or revert and use a .ocean-release file instead"
            )
            continue

        print(f"  {target.label}: missing release")
        errors.append(
            f"{target.label}: add a release file ({target.release_hint}) "
            "or manually bump version and changelog"
        )

    if errors:
        print(f"Validation finished with {len(errors)} error(s)")
    else:
        print("Validation passed")

    return errors


def _release_files_by_target(
    git: GitContext,
    base_ref: str,
    head_ref: str,
) -> dict[tuple[str, str], list[Path]]:
    by_target: dict[tuple[str, str], list[Path]] = {}
    for relative_path in git.release_files_added_in_diff(base_ref, head_ref):
        target = target_from_release_path(git.repo_root, relative_path)
        key = (target.kind, target.name)
        by_target.setdefault(key, []).append(
            Path(git.repo_root, *Path(relative_path).parts)
        )
    return by_target


def _validate_declarative(
    git: GitContext,
    target: ReleaseTarget,
    release_files: list[Path],
) -> list[str]:
    errors: list[str] = []
    try:
        current_version = parse_version(git.read_worktree(target.pyproject_path))
        errors.extend(validate_target_version_label(target.label, current_version))
    except ValueError as exc:
        return [f"{target.label}: {exc}"]

    for release_file in release_files:
        try:
            parse_release_file(release_file, git.read_worktree(release_file))
        except (OSError, ValueError) as exc:
            errors.append(str(exc))

    return errors


def _validate_manual_version(git: GitContext, target: ReleaseTarget) -> list[str]:
    try:
        current_version = parse_version(git.read_worktree(target.pyproject_path))
        return validate_target_version_label(target.label, current_version)
    except ValueError as exc:
        return [f"{target.label}: {exc}"]
