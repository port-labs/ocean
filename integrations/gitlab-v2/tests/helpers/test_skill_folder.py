from typing import Any, AsyncIterator, Optional

import pytest

from gitlab.helpers.skill_folder import (
    MAX_SKILL_BUNDLE_SIZE,
    MAX_SKILL_FOLDER_DEPTH,
    fetch_skill_folder_files,
    select_skill_folder_files,
    skill_dir_prefix,
)

PROJECT = {"id": 1, "path_with_namespace": "group/project"}


def _blob(path: str, mode: str = "100644") -> dict[str, Any]:
    return {"type": "blob", "path": path, "mode": mode}


def _selected_paths(tree: list[dict[str, Any]], skill_md_path: str) -> list[str]:
    return [entry["path"] for entry in select_skill_folder_files(tree, skill_md_path)]


class FakeRest:
    def __init__(self, contents: dict[str, Any]) -> None:
        self.contents = contents
        self.file_calls: list[tuple[str, str]] = []

    async def get_file_data(
        self, project_id: str, file_path: str, ref: str
    ) -> dict[str, Any]:
        self.file_calls.append((file_path, ref))
        value = self.contents.get(file_path)
        if isinstance(value, BaseException):
            raise value
        return {} if value is None else {"content": value}


class FakeFolderClient:
    """Serves one repository tree and file contents keyed by path."""

    def __init__(self, tree: list[dict[str, Any]], contents: dict[str, Any]) -> None:
        self.tree = tree
        self.rest = FakeRest(contents)
        self.tree_calls: list[tuple[str, str, Optional[bool]]] = []

    async def get_repository_tree(
        self,
        project: dict[str, Any],
        path: str,
        ref: str = "main",
        *,
        recursive: Optional[bool] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        self.tree_calls.append((path, ref, recursive))
        prefix = f"{path}/" if path else ""
        yield [entry for entry in self.tree if entry["path"].startswith(prefix)]


class TestSelectSkillFolderFiles:
    def test_skill_dir_prefix(self) -> None:
        assert skill_dir_prefix("skills/hello/SKILL.md") == "skills/hello/"
        assert skill_dir_prefix("SKILL.md") == ""

    def test_selects_nested_text_files(self) -> None:
        tree = [
            _blob("skills/hello/SKILL.md"),
            _blob("skills/hello/references/api.md"),
            _blob("skills/hello/scripts/run.py"),
            _blob("skills/hello/notes.TXT"),
            {"type": "tree", "path": "skills/hello/references"},
        ]
        assert _selected_paths(tree, "skills/hello/SKILL.md") == [
            "skills/hello/references/api.md",
            "skills/hello/scripts/run.py",
            "skills/hello/notes.TXT",
        ]

    def test_excludes_non_text_symlinks_and_outside_files(self) -> None:
        tree = [
            _blob("skills/hello/SKILL.md"),
            _blob("skills/hello/assets/logo.png"),
            _blob("skills/hello/Makefile"),
            _blob("skills/hello/link.md", mode="120000"),
            _blob("skills/hello-world/references/api.md"),
            _blob("skills/other/references/api.md"),
            _blob("README.md"),
        ]
        assert _selected_paths(tree, "skills/hello/SKILL.md") == []

    def test_excludes_files_of_nested_skills(self) -> None:
        tree = [
            _blob("skills/parent/SKILL.md"),
            _blob("skills/parent/references/api.md"),
            _blob("skills/parent/child/skill.md"),
            _blob("skills/parent/child/references/child.md"),
        ]
        assert _selected_paths(tree, "skills/parent/SKILL.md") == [
            "skills/parent/references/api.md"
        ]
        assert _selected_paths(tree, "skills/parent/child/skill.md") == [
            "skills/parent/child/references/child.md"
        ]

    def test_respects_depth_limit(self) -> None:
        allowed = "skills/hello/" + "d/" * MAX_SKILL_FOLDER_DEPTH + "ok.md"
        too_deep = "skills/hello/" + "d/" * (MAX_SKILL_FOLDER_DEPTH + 1) + "deep.md"
        tree = [_blob("skills/hello/SKILL.md"), _blob(allowed), _blob(too_deep)]
        assert _selected_paths(tree, "skills/hello/SKILL.md") == [allowed]

    def test_root_level_skill_uses_whole_repository(self) -> None:
        tree = [_blob("SKILL.md"), _blob("references/api.md")]
        assert _selected_paths(tree, "SKILL.md") == ["references/api.md"]


@pytest.mark.asyncio
class TestFetchSkillFolderFiles:
    async def test_returns_sorted_relative_files_read_at_ref(self) -> None:
        client = FakeFolderClient(
            tree=[
                _blob("skills/hello/SKILL.md"),
                _blob("skills/hello/scripts/run.py"),
                _blob("skills/hello/references/api.md"),
            ],
            contents={
                "skills/hello/scripts/run.py": "print(1)",
                "skills/hello/references/api.md": "# API",
            },
        )

        files = await fetch_skill_folder_files(
            client,  # type: ignore[arg-type]
            project=PROJECT,
            ref="abc123",
            skill_md_path="skills/hello/SKILL.md",
            skill_md_size=10,
        )

        assert files == [
            {"path": "references/api.md", "content": "# API"},
            {"path": "scripts/run.py", "content": "print(1)"},
        ]
        assert client.tree_calls == [("skills/hello", "abc123", True)]
        assert {ref for _, ref in client.rest.file_calls} == {"abc123"}

    async def test_root_level_skill_lists_whole_repository(self) -> None:
        client = FakeFolderClient(
            tree=[_blob("SKILL.md"), _blob("notes.md")],
            contents={"notes.md": "notes"},
        )

        files = await fetch_skill_folder_files(
            client,  # type: ignore[arg-type]
            project=PROJECT,
            ref="main",
            skill_md_path="SKILL.md",
            skill_md_size=10,
        )

        assert files == [{"path": "notes.md", "content": "notes"}]
        assert client.tree_calls == [("", "main", True)]

    async def test_size_limit_is_inclusive(self) -> None:
        skill_md_size = 100
        at_limit = "a" * (MAX_SKILL_BUNDLE_SIZE - skill_md_size)
        tree = [_blob("skills/hello/SKILL.md"), _blob("skills/hello/big.md")]

        kept = await fetch_skill_folder_files(
            FakeFolderClient(tree, {"skills/hello/big.md": at_limit}),  # type: ignore[arg-type]
            project=PROJECT,
            ref="main",
            skill_md_path="skills/hello/SKILL.md",
            skill_md_size=skill_md_size,
        )
        dropped = await fetch_skill_folder_files(
            FakeFolderClient(tree, {"skills/hello/big.md": at_limit + "a"}),  # type: ignore[arg-type]
            project=PROJECT,
            ref="main",
            skill_md_path="skills/hello/SKILL.md",
            skill_md_size=skill_md_size,
        )

        assert kept == [{"path": "big.md", "content": at_limit}]
        assert dropped is None

    async def test_skips_undecodable_and_missing_files(self) -> None:
        client = FakeFolderClient(
            tree=[
                _blob("skills/hello/SKILL.md"),
                _blob("skills/hello/latin1.txt"),
                _blob("skills/hello/gone.md"),
                _blob("skills/hello/ok.md"),
            ],
            contents={
                "skills/hello/latin1.txt": UnicodeDecodeError(
                    "utf-8", b"\xe9", 0, 1, "invalid continuation byte"
                ),
                "skills/hello/ok.md": "ok",
            },
        )

        files = await fetch_skill_folder_files(
            client,  # type: ignore[arg-type]
            project=PROJECT,
            ref="main",
            skill_md_path="skills/hello/SKILL.md",
            skill_md_size=10,
        )

        assert files == [{"path": "ok.md", "content": "ok"}]
