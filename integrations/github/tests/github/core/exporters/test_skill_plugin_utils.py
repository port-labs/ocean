from typing import Any

from github.core.exporters.skill_exporter.references import (
    MAX_REFERENCE_DEPTH,
    glob_base_dir,
    select_reference_files,
    skill_dir_prefix,
)
from github.core.exporters.skill_exporter.utils import (
    _build_skill,
    _infer_skill_root,
    _parse_skill_markdown,
    build_skill_raw_item,
)
from github.core.exporters.plugin_exporter.utils import (
    build_plugin_raw_item,
    empty_plugin,
    normalize_plugin,
)

REPOSITORY = {"name": "example-skills", "full_name": "acme/example-skills"}


class TestSkillUtils:
    def test_infer_skill_root(self) -> None:
        globs = [".cursor/skills/**/SKILL.md", "skills/**/SKILL.md"]
        assert (
            _infer_skill_root(".cursor/skills/ponytail/SKILL.md", globs)
            == ".cursor/skills"
        )
        assert _infer_skill_root("skills/hello/SKILL.md", globs) == "skills"

    def test_build_skill_multi_segment_root(self) -> None:
        skill = _build_skill(
            skill_md_path=".cursor/skills/hello/SKILL.md",
            content="# Hello",
            path_globs=[".cursor/skills/**/SKILL.md"],
        )
        assert skill.root == ".cursor/skills"
        assert skill.path == ".cursor/skills/hello"
        assert skill.instructions == "# Hello"

    def test_parse_skill_markdown(self) -> None:
        content = """---
name: hello-skill
description: A minimal example
---

# Hello

Body text.
"""
        fm, body = _parse_skill_markdown(content)
        assert fm["name"] == "hello-skill"
        assert fm["description"] == "A minimal example"
        assert body.startswith("# Hello")

    def test_parse_skill_markdown_no_frontmatter(self) -> None:
        fm, body = _parse_skill_markdown("# Just markdown")
        assert fm == {}
        assert body == "# Just markdown"

    def test_parse_skill_markdown_unclosed_fence(self) -> None:
        fm, body = _parse_skill_markdown("---\nname: x")
        assert fm == {}
        assert body.startswith("---")

    def test_build_skill_raw_item_always_includes_body(self) -> None:
        content = """---
name: hello-skill
description: A minimal example
---

# Hello
"""
        item = build_skill_raw_item(
            skill_md_path="skills/hello-skill/SKILL.md",
            content=content,
            repository=REPOSITORY,
            branch="main",
            organization="acme",
            path_globs=["skills/**/SKILL.md"],
            blob_sha="e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
        )
        skill = item["skill"]
        assert skill["name"] == "hello-skill"
        assert skill["description"] == "A minimal example"
        assert "# Hello" in skill["instructions"]
        assert skill["path"] == "skills/hello-skill"
        assert skill["skillMdPath"] == "skills/hello-skill/SKILL.md"
        assert skill["root"] == "skills"
        assert skill["blob_sha"] == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
        assert item["__repository"] == REPOSITORY
        assert item["__branch"] == "main"
        assert item["__organization"] == "acme"

    def test_build_skill_raw_item_blob_sha_defaults_to_none(self) -> None:
        item = build_skill_raw_item(
            skill_md_path="skills/hello-skill/SKILL.md",
            content="# No sha provided",
            repository=REPOSITORY,
            branch="main",
            organization="acme",
            path_globs=["skills/**/SKILL.md"],
        )
        assert item["skill"]["blob_sha"] is None

    def test_build_skill_raw_item_name_fallback(self) -> None:
        item = build_skill_raw_item(
            skill_md_path="skills/my-skill/SKILL.md",
            content="# No frontmatter",
            repository=REPOSITORY,
            branch="main",
            organization="acme",
            path_globs=["skills/**/SKILL.md"],
        )
        assert item["skill"]["name"] == "my-skill"
        assert item["skill"]["description"] == ""

    def test_build_skill_raw_item_delete_stub_matches_upsert_identity(self) -> None:
        """Webhook deletes reuse the builder so identifiers stay identical."""
        kwargs = {
            "skill_md_path": ".cursor/skills/hello/SKILL.md",
            "repository": REPOSITORY,
            "branch": "main",
            "organization": "acme",
            "path_globs": [".cursor/skills/**/SKILL.md"],
        }
        upserted = build_skill_raw_item(
            content="---\nname: hello\n---\n# Hi",
            blob_sha="a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
            **kwargs,  # type: ignore[arg-type]
        )
        deleted = build_skill_raw_item(content="", **kwargs)  # type: ignore[arg-type]

        assert deleted["skill"]["path"] == upserted["skill"]["path"]
        assert deleted["skill"]["root"] == upserted["skill"]["root"]
        assert deleted["skill"]["skillMdPath"] == upserted["skill"]["skillMdPath"]
        assert deleted["skill"]["name"] == "hello"
        assert deleted["skill"]["blob_sha"] is None
        assert (
            upserted["skill"]["blob_sha"] == "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3"
        )


def _blob(path: str, size: int = 10, mode: str = "100644") -> dict[str, Any]:
    return {"type": "blob", "path": path, "size": size, "mode": mode}


def _selected_paths(tree: list[dict[str, Any]], skill_md_path: str) -> list[str]:
    return [entry["path"] for entry in select_reference_files(tree, skill_md_path)]


class TestSkillReferences:
    def test_skill_dir_prefix(self) -> None:
        assert skill_dir_prefix("skills/hello/SKILL.md") == "skills/hello/"
        assert skill_dir_prefix("SKILL.md") == ""

    def test_glob_base_dir(self) -> None:
        assert glob_base_dir("skills/**/SKILL.md") == "skills/"
        assert glob_base_dir(".claude/skills/*/SKILL.md") == ".claude/skills/"
        assert glob_base_dir("skills/hello/SKILL.md") == "skills/hello/"
        assert glob_base_dir("**/SKILL.md") == ""
        assert glob_base_dir("SKILL.md") == ""

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
            _blob("skills/parent/child/SKILL.md"),
            _blob("skills/parent/child/references/child.md"),
        ]
        assert _selected_paths(tree, "skills/parent/SKILL.md") == [
            "skills/parent/references/api.md"
        ]
        assert _selected_paths(tree, "skills/parent/child/SKILL.md") == [
            "skills/parent/child/references/child.md"
        ]

    def test_respects_depth_limit(self) -> None:
        allowed = "skills/hello/" + "d/" * MAX_REFERENCE_DEPTH + "ok.md"
        too_deep = "skills/hello/" + "d/" * (MAX_REFERENCE_DEPTH + 1) + "deep.md"
        tree = [_blob("skills/hello/SKILL.md"), _blob(allowed), _blob(too_deep)]
        assert _selected_paths(tree, "skills/hello/SKILL.md") == [allowed]

    def test_root_level_skill_uses_whole_repository(self) -> None:
        tree = [_blob("SKILL.md"), _blob("references/api.md")]
        assert _selected_paths(tree, "SKILL.md") == ["references/api.md"]


class TestPluginUtils:
    def test_normalize_plugin_superpowers_shape(self) -> None:
        repository = {"name": "superpowers", "full_name": "obra/superpowers"}
        manifests = {
            ".claude-plugin/plugin.json": {
                "name": "superpowers",
                "description": "Core skills",
                "version": "6.1.1",
            },
            ".claude-plugin/marketplace.json": {"name": "superpowers-dev"},
            ".cursor-plugin/plugin.json": {
                "name": "superpowers",
                "displayName": "Superpowers",
                "version": "6.1.1",
            },
        }
        plugin = normalize_plugin(
            repository=repository,
            manifests=manifests,
            providers=["claude", "cursor", "codex"],
        )
        assert plugin is not None
        dumped = plugin.model_dump(by_alias=True)
        assert dumped["name"] == "superpowers"
        assert dumped["displayName"] == "Superpowers"
        assert dumped["supports"]["claude"] is True
        assert dumped["supports"]["cursor"] is True
        assert dumped["supports"]["codex"] is False
        assert dumped["claude"]["marketplaceName"] == "superpowers-dev"
        assert dumped["codex"] == {}

    def test_normalize_plugin_directory_only(self) -> None:
        repository = {"name": "opencode-plugin", "full_name": "acme/opencode-plugin"}
        plugin = normalize_plugin(
            repository=repository,
            manifests={},
            providers=["opencode", "pi"],
            directory_supports={"opencode"},
        )
        assert plugin is not None
        assert plugin.name == "opencode-plugin"
        assert plugin.supports["opencode"] is True
        assert plugin.supports["pi"] is False
        assert plugin.model_dump()["opencode"] == {"detected": True}

    def test_normalize_plugin_marketplace_only_uses_first_entry(self) -> None:
        repository = {"name": "agent-marketplace"}
        plugin = normalize_plugin(
            repository=repository,
            manifests={
                ".agents/plugins/marketplace.json": {
                    "name": "acme-marketplace",
                    "interface": {"displayName": "Acme Agents"},
                    "plugins": [{"name": "acme-agents", "version": "0.4.0"}],
                }
            },
            providers=["agents"],
        )
        assert plugin is not None
        dumped = plugin.model_dump(by_alias=True)
        assert dumped["name"] == "acme-agents"
        assert dumped["displayName"] == "Acme Agents"
        assert dumped["version"] == "0.4.0"
        assert dumped["agents"]["marketplaceName"] == "acme-marketplace"

    def test_normalize_plugin_returns_none_without_evidence(self) -> None:
        assert (
            normalize_plugin(
                repository={"name": "plain-repo"},
                manifests={},
                providers=["claude", "cursor"],
            )
            is None
        )

    def test_normalize_plugin_ignores_unselected_providers(self) -> None:
        plugin = normalize_plugin(
            repository={"name": "repo"},
            manifests={".cursor-plugin/plugin.json": {"name": "only-cursor"}},
            providers=["claude"],
        )
        assert plugin is None

    def test_build_plugin_raw_item(self) -> None:
        item = build_plugin_raw_item(
            plugin=empty_plugin(name="superpowers"),
            repository={"name": "superpowers"},
            branch="main",
            organization="obra",
        )
        assert item["plugin"]["name"] == "superpowers"
        assert item["plugin"]["displayName"] == "superpowers"
        assert item["plugin"]["supports"]["claude"] is False
        assert item["plugin"]["claude"] == {}
        assert item["__branch"] == "main"
        assert item["__organization"] == "obra"
