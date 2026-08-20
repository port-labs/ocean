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


def apply(
    git: GitContext,
    *,
    main_ref: str,
    merge_sha: str | None = None,
    base_ref: str | None = None,
    head_ref: str | None = None,
) -> list[AppliedRelease]:
    if head_ref is not None:
        parent_ref = base_ref or f"{head_ref}^"
        compare_head = head_ref
        release_files = git.release_files_added_in_diff(parent_ref, compare_head)
        source = f"{parent_ref}...{compare_head}"
    elif merge_sha is not None:
        parent_ref = f"{merge_sha}^"
        compare_head = merge_sha
        release_files = git.release_files_added_in_diff(merge_sha)
        source = merge_sha
    else:
        raise ValueError("Either merge_sha or head_ref is required")

    applied: list[AppliedRelease] = []
    print(f"Applying releases for {source} (version base: {main_ref})")
    if not release_files:
        print("No release files added")
        return applied

    print(f"Found {len(release_files)} release file(s)")
    for relative_path in release_files:
        print(f"Processing {relative_path}")
        target = target_from_release_path(git.repo_root, relative_path)

        if git.has_version_changed(parent_ref, compare_head, target.pyproject_path):
            print(f"Skipping {target.label}: manual version bump detected in {source}")
            continue

        release_path = Path(git.repo_root, *Path(relative_path).parts)
        intent = parse_release_file(release_path, git.read_worktree(release_path))
        release = _apply_intent(
            git,
            target,
            intent,
            main_ref=main_ref,
            release_file_relative=relative_path,
        )
        applied.append(release)
        print(
            f"Applied {target.label}: {release.previous_version} -> {release.new_version}"
        )

    print(f"Applied {len(applied)} release(s)")
    return applied


def _apply_intent(
    git: GitContext,
    target: ReleaseTarget,
    intent: ReleaseIntent,
    *,
    main_ref: str,
    release_file_relative: str,
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
