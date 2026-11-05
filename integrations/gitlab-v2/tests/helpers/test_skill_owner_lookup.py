from typing import Any, AsyncIterator, Optional

from gitlab.helpers.skill_folder import find_owning_skill_md_paths

PROJECT = {"id": 1, "path_with_namespace": "group/project"}
GLOBS = [".cursor/skills/**/SKILL.md", "tools/**/SKILL.md"]


def _blob(path: str) -> dict[str, Any]:
    return {"type": "blob", "path": path, "mode": "100644"}


class FakeFolderListingClient:
    """Serves a repository tree and records each folder listing request."""

    def __init__(self, tree: list[dict[str, Any]]) -> None:
        self.tree = tree
        self.tree_calls: list[tuple[str, Optional[bool]]] = []

    async def get_repository_tree(
        self,
        project: dict[str, Any],
        path: str,
        ref: str = "main",
        *,
        recursive: Optional[bool] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        self.tree_calls.append((path, recursive))
        prefix = f"{path}/" if path else ""
        yield [
            entry
            for entry in self.tree
            if entry["path"].startswith(prefix)
            and (recursive or "/" not in entry["path"][len(prefix) :])
        ]


TREE = [
    _blob(".cursor/skills/billing/SKILL.md"),
    _blob(".cursor/skills/billing/refund/SKILL.md"),
    _blob(".cursor/skills/billing/refund/helper.py"),
    _blob(".cursor/skills/billing/invoice.md"),
    _blob("tools/lint/SKILL.md"),
    _blob("tools/lint/rules.yaml"),
    _blob("docs/SKILL.md"),
    _blob("README.md"),
]


async def test_file_belongs_to_nearest_skill_only() -> None:
    client = FakeFolderListingClient(TREE)

    owners = await find_owning_skill_md_paths(
        client,  # type: ignore[arg-type]
        PROJECT,
        "main",
        {".cursor/skills/billing/refund/helper.py"},
        GLOBS,
    )

    assert owners == {".cursor/skills/billing/refund/SKILL.md"}
    assert client.tree_calls == [(".cursor/skills/billing/refund", False)]


async def test_file_in_outer_skill_folder_belongs_to_outer_skill() -> None:
    client = FakeFolderListingClient(TREE)

    owners = await find_owning_skill_md_paths(
        client,  # type: ignore[arg-type]
        PROJECT,
        "main",
        {".cursor/skills/billing/invoice.md"},
        GLOBS,
    )

    assert owners == {".cursor/skills/billing/SKILL.md"}


async def test_folders_outside_skill_roots_are_not_listed() -> None:
    client = FakeFolderListingClient(TREE)

    owners = await find_owning_skill_md_paths(
        client,  # type: ignore[arg-type]
        PROJECT,
        "main",
        {"README.md", "docs/guide.md"},
        GLOBS,
    )

    assert owners == set()
    assert client.tree_calls == []


async def test_folder_listed_once_for_many_changed_files() -> None:
    client = FakeFolderListingClient(TREE)

    owners = await find_owning_skill_md_paths(
        client,  # type: ignore[arg-type]
        PROJECT,
        "main",
        {
            "tools/lint/rules.yaml",
            "tools/lint/config.toml",
        },
        GLOBS,
    )

    assert owners == {"tools/lint/SKILL.md"}
    assert client.tree_calls == [("tools/lint", False)]


async def test_non_matching_skill_name_is_not_an_owner() -> None:
    client = FakeFolderListingClient(
        [_blob(".cursor/skills/notes/skill.txt"), _blob(".cursor/skills/notes/a.md")]
    )

    owners = await find_owning_skill_md_paths(
        client,  # type: ignore[arg-type]
        PROJECT,
        "main",
        {".cursor/skills/notes/a.md"},
        GLOBS,
    )

    assert owners == set()
