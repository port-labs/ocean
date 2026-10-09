from typing import Any, Optional

import pytest

from github.core.exporters.skill_exporter.utils import (
    _build_skill,
    _infer_skill_root,
    _parse_skill_markdown,
    build_skill_raw_item,
)
from github.core.exporters.plugin_exporter.utils import (
    PluginProvider,
    build_plugin_raw_item,
    empty_plugin,
    find_plugin_roots,
    match_marker,
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


class TestPluginUtils:
    def test_normalize_plugin_superpowers_shape(self) -> None:
        plugin = normalize_plugin(
            repository={"name": "superpowers"},
            manifests={
                ".claude-plugin/plugin.json": {
                    "name": "superpowers",
                    "description": "Core skills",
                    "version": "6.1.1",
                },
                ".claude-plugin/marketplace.json": {"name": "superpowers-dev"},
                ".cursor-plugin/plugin.json": {
                    "name": "superpowers",
                    "displayName": "Superpowers",
                },
            },
            providers=["claude", "cursor", "codex"],
            path="plugins/superpowers",
        )
        assert plugin is not None
        dumped = plugin.model_dump(by_alias=True)
        assert dumped["displayName"] == "Superpowers"
        assert dumped["path"] == "plugins/superpowers"
        assert dumped["supports"]["claude"] is dumped["supports"]["cursor"] is True
        assert dumped["supports"]["codex"] is False
        assert dumped["claude"]["marketplaceName"] == "superpowers-dev"
        assert dumped["codex"] == {}

    def test_normalize_plugin_directory_only(self) -> None:
        plugin = normalize_plugin(
            repository={"name": "opencode-plugin"},
            manifests={},
            providers=["opencode", "pi"],
            path="plugins/hooks",
            directory_supports={"opencode"},
        )
        assert plugin is not None
        assert plugin.name == "opencode-plugin"
        assert plugin.path == "plugins/hooks"
        assert plugin.supports["opencode"] is True
        assert plugin.supports["pi"] is False
        assert plugin.model_dump()["opencode"] == {"detected": True}

    @pytest.mark.parametrize(
        "manifests,providers",
        [
            # A marketplace file never creates a plugin, even with listed entries.
            (
                {".claude-plugin/marketplace.json": {"plugins": [{"name": "first"}]}},
                ["claude"],
            ),
            (
                {".agents/plugins/marketplace.json": {"plugins": [{"name": "x"}]}},
                ["agents"],
            ),
            ({}, ["claude", "cursor"]),
            ({".cursor-plugin/plugin.json": {"name": "cursor"}}, ["claude"]),
        ],
    )
    def test_normalize_plugin_returns_none_without_primary_manifest(
        self, manifests: dict[str, Any], providers: list[PluginProvider]
    ) -> None:
        assert (
            normalize_plugin(
                repository={"name": "repo"}, manifests=manifests, providers=providers
            )
            is None
        )

    def test_build_plugin_raw_item_for_delete_keeps_path(self) -> None:
        item = build_plugin_raw_item(
            plugin=empty_plugin(
                name="frontend-toolkit", path="plugins/frontend-toolkit"
            ),
            repository=REPOSITORY,
            branch="main",
            organization="acme",
        )
        assert item["plugin"]["name"] == item["plugin"]["displayName"]
        assert item["plugin"]["path"] == "plugins/frontend-toolkit"
        assert item["plugin"]["supports"]["claude"] is False
        assert item["plugin"]["claude"] == {}
        assert item["__branch"] == "main"
        assert item["__organization"] == "acme"


ALL_PROVIDERS: list[PluginProvider] = [
    "claude",
    "cursor",
    "codex",
    "agents",
    "kimi",
    "opencode",
    "pi",
    "antigravity",
]


class TestMatchMarker:
    @pytest.mark.parametrize(
        "path,expected",
        [
            (".claude-plugin/plugin.json", ("claude", "")),
            (".claude-plugin/marketplace.json", ("claude", "")),
            ("plugins/a/.cursor-plugin/plugin.json", ("cursor", "plugins/a")),
            ("a/b/.agents/plugins/marketplace.json", ("agents", "a/b")),
            # Bare filename marker: any depth.
            ("gemini-extension.json", ("antigravity", "")),
            (
                "plugins/gravity/gemini-extension.json",
                ("antigravity", "plugins/gravity"),
            ),
            # Directory markers: root is the parent of the marker directory.
            (".opencode/plugins/x.ts", ("opencode", "")),
            ("plugins/hooks/.opencode/plugins/sub/x.ts", ("opencode", "plugins/hooks")),
            (".pi/extensions/x.ts", ("pi", "")),
            # Not markers.
            ("not-gemini-extension.json", None),
            ("x.claude-plugin/plugin.json", None),
            ("plugins/a/skills/x/SKILL.md", None),
            (".opencode/plugins", None),
            (".opencode/plugins/", None),
            ("plugins/hooks/.pi/extensions", None),
            # Ignored segments.
            ("node_modules/foo/.claude-plugin/plugin.json", None),
            ("vendor/bar/.cursor-plugin/plugin.json", None),
            (".git/hooks/.codex-plugin/plugin.json", None),
            ("dist/pkg/.kimi-plugin/plugin.json", None),
            (
                "plugins/dist-kit/.claude-plugin/plugin.json",
                ("claude", "plugins/dist-kit"),
            ),
        ],
    )
    def test_match_marker(self, path: str, expected: Optional[tuple[str, str]]) -> None:
        assert match_marker(path, ALL_PROVIDERS) == expected

    def test_only_selected_providers_match(self) -> None:
        assert match_marker(".cursor-plugin/plugin.json", ["claude"]) is None


class TestFindPluginRoots:
    def test_groups_paths_by_root_and_provider(self) -> None:
        paths = [
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            "plugins/a/.claude-plugin/plugin.json",
            "plugins/a/.cursor-plugin/plugin.json",
            "plugins/hooks/.opencode/plugins/hook.ts",
        ]
        roots = find_plugin_roots(paths, ALL_PROVIDERS)

        assert set(roots) == {"", "plugins/a", "plugins/hooks"}
        assert roots[""] == {
            "claude": {".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"}
        }
        assert set(roots["plugins/a"]) == {"claude", "cursor"}
        assert roots["plugins/hooks"] == {
            "opencode": {"plugins/hooks/.opencode/plugins/hook.ts"}
        }

    def test_max_depth_counts_root_segments(self) -> None:
        paths = [
            ".claude-plugin/plugin.json",
            "toolkit/.claude-plugin/plugin.json",
            "plugins/a/.claude-plugin/plugin.json",
        ]
        assert set(find_plugin_roots(paths, ["claude"], max_depth=1)) == {"", "toolkit"}
        assert set(find_plugin_roots(paths, ["claude"])) == {
            "",
            "toolkit",
            "plugins/a",
        }
