"""Applies declarative releases after merge to main."""

from __future__ import annotations

from pathlib import Path

from .changelog import apply_towncrier_changelog, cleanup_release_file
from .git_context import GitContext
from .models import AppliedRelease, ReleaseIntent, ReleaseTarget
from .release_file import parse_release_file, target_from_release_path
from .version import (
    bump_version,
    parse_integration_type,
    parse_version,
    set_version,
)


def apply(git: GitContext, *, merge_sha: str, main_ref: str) -> list[AppliedRelease]:
    parent_ref = f"{merge_sha}^"
    applied: list[AppliedRelease] = []
    release_files = git.release_files_added_in_diff(merge_sha)

    print(f"Applying releases for merge {merge_sha} (version base: {main_ref})")
    if not release_files:
        print("No release files added in merge commit")
        return applied

    print(f"Found {len(release_files)} release file(s) in merge commit")
    applied_keys: set[tuple[str, str]] = set()
    core_intent: ReleaseIntent | None = None
    core_release_relative: str | None = None

    for relative_path in release_files:
        print(f"Processing {relative_path}")
        target = target_from_release_path(git.repo_root, relative_path)
        release_path = Path(git.repo_root, *Path(relative_path).parts)
        intent = parse_release_file(release_path, git.read_worktree(release_path))
        if target.kind == "core":
            core_intent = intent
            core_release_relative = relative_path

        if git.has_version_changed(parent_ref, merge_sha, target.pyproject_path):
            print(
                f"Skipping {target.label}: manual version bump detected in merge commit"
            )
            continue

        release = _apply_intent(
            git,
            target,
            intent,
            main_ref=main_ref,
            release_file_relative=relative_path,
            cleanup=True,
        )
        applied.append(release)
        applied_keys.add((target.kind, target.name))
        print(
            f"Applied {target.label}: {release.previous_version} -> {release.new_version}"
        )

    if core_intent is not None and core_release_relative is not None:
        applied.extend(
            _apply_core_intent_to_changed_integrations(
                git,
                core_intent,
                parent_ref=parent_ref,
                merge_sha=merge_sha,
                main_ref=main_ref,
                release_file_relative=core_release_relative,
                already_applied=applied_keys,
            )
        )

    print(f"Applied {len(applied)} release(s)")
    return applied


def _apply_core_intent_to_changed_integrations(
    git: GitContext,
    intent: ReleaseIntent,
    *,
    parent_ref: str,
    merge_sha: str,
    main_ref: str,
    release_file_relative: str,
    already_applied: set[tuple[str, str]],
) -> list[AppliedRelease]:
    """Bump integrations changed alongside core when only a core intent exists."""
    applied: list[AppliedRelease] = []
    for target in git.changed_release_targets(parent_ref, merge_sha):
        if target.kind != "integration":
            continue
        if (target.kind, target.name) in already_applied:
            continue
        if git.has_version_changed(parent_ref, merge_sha, target.pyproject_path):
            print(
                f"Skipping {target.label}: manual version bump detected in merge commit"
            )
            continue

        print(f"Processing {target.label} via core release intent")
        release = _apply_intent(
            git,
            target,
            intent,
            main_ref=main_ref,
            release_file_relative=release_file_relative,
            cleanup=False,
        )
        applied.append(release)
        print(
            f"Applied {target.label}: {release.previous_version} -> {release.new_version}"
        )
    return applied


def _apply_intent(
    git: GitContext,
    target: ReleaseTarget,
    intent: ReleaseIntent,
    *,
    main_ref: str,
    release_file_relative: str,
    cleanup: bool = True,
) -> AppliedRelease:
    current_version = parse_version(git.read_at_ref(main_ref, target.pyproject_path))
    new_version = bump_version(current_version, intent.bump)
    print(f"  Bumping {target.label} from {current_version} to {new_version}")

    pyproject_content = git.read_worktree(target.pyproject_path)
    target.pyproject_path.write_text(
        set_version(pyproject_content, new_version),
        encoding="utf-8",
    )
    apply_towncrier_changelog(
        target,
        new_version,
        intent.changelog_type,
        intent.changelog,
    )
    if cleanup:
        cleanup_release_file(intent.path)

    return AppliedRelease(
        target=target,
        previous_version=current_version,
        new_version=new_version,
        bump=intent.bump,
        changelog=intent.changelog,
        release_file=release_file_relative,
        integration_type=parse_integration_type(pyproject_content, target.name),
        context_dir=target.work_dir.relative_to(git.repo_root).as_posix(),
    )
