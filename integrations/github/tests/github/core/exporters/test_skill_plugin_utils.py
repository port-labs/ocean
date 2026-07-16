from github.core.exporters.skill_exporter.utils import (
    build_skill_object,
    match_skill_root,
    parse_skill_markdown,
    path_under_roots_or_extra,
    roots_to_globs,
)
from github.core.exporters.plugin_exporter.utils import normalize_plugin


class TestSkillUtils:
    def test_roots_to_globs(self) -> None:
        globs = roots_to_globs(["skills", ".cursor/skills"])
        assert "skills/**/SKILL.md" in globs
        assert "skills/SKILL.md" in globs
        assert ".cursor/skills/**/SKILL.md" in globs

    def test_match_skill_root(self) -> None:
        roots = [".cursor/skills", "skills"]
        assert match_skill_root("skills/hello/SKILL.md", roots) == "skills"
        assert (
            match_skill_root(".cursor/skills/ponytail/SKILL.md", roots)
            == ".cursor/skills"
        )
        assert match_skill_root("other/SKILL.md", roots) is None

    def test_path_under_roots_or_extra(self) -> None:
        roots = ["skills"]
        assert path_under_roots_or_extra("skills/hello/SKILL.md", roots, [])
        assert path_under_roots_or_extra(
            "packages/ai/skills/x/SKILL.md",
            roots,
            ["packages/**/SKILL.md"],
        )
        assert path_under_roots_or_extra(
            ".cursor/skills/x/SKILL.md",
            [],
            [".cursor/**/SKILL.md"],
        )
        assert not path_under_roots_or_extra("packages/ai/skills/x/SKILL.md", roots, [])

    def test_build_skill_object_multi_segment_root(self) -> None:
        skill = build_skill_object(
            skill_md_path=".cursor/skills/hello/SKILL.md",
            content="# Hello",
            content_mode="skill.md",
            roots=[".cursor/skills"],
        )
        assert skill["root"] == ".cursor/skills"
        assert skill["path"] == ".cursor/skills/hello"

    def test_parse_skill_markdown(self) -> None:
        content = """---
name: hello-skill
description: A minimal example
---

# Hello

Body text.
"""
        fm, body = parse_skill_markdown(content)
        assert fm["name"] == "hello-skill"
        assert fm["description"] == "A minimal example"
        assert body.startswith("# Hello")

    def test_parse_skill_markdown_no_frontmatter(self) -> None:
        fm, body = parse_skill_markdown("# Just markdown")
        assert fm == {}
        assert body == "# Just markdown"

    def test_build_skill_object_skill_md_mode(self) -> None:
        content = """---
name: hello-skill
description: A minimal example
---

# Hello
"""
        skill = build_skill_object(
            skill_md_path="skills/hello-skill/SKILL.md",
            content=content,
            content_mode="skill.md",
            roots=["skills"],
        )
        assert skill["name"] == "hello-skill"
        assert skill["description"] == "A minimal example"
        assert skill["instructions"] is not None
        assert "# Hello" in skill["instructions"]
        assert skill["path"] == "skills/hello-skill"
        assert skill["skillMdPath"] == "skills/hello-skill/SKILL.md"
        assert skill["root"] == "skills"

    def test_build_skill_object_frontmatter_mode(self) -> None:
        content = """---
name: hello-skill
description: A minimal example
---

# Hello
"""
        skill = build_skill_object(
            skill_md_path="skills/hello-skill/SKILL.md",
            content=content,
            content_mode="frontmatter",
            roots=["skills"],
        )
        assert skill["instructions"] is None
        assert skill["name"] == "hello-skill"

    def test_build_skill_object_name_fallback(self) -> None:
        skill = build_skill_object(
            skill_md_path="skills/my-skill/SKILL.md",
            content="# No frontmatter",
            content_mode="skill.md",
            roots=["skills"],
        )
        assert skill["name"] == "my-skill"
        assert skill["description"] == ""


class TestPluginUtils:
    def test_normalize_plugin_superpowers_shape(self) -> None:
        repository = {"name": "superpowers"}
        manifests = {
            ".claude-plugin/plugin.json": {
                "name": "superpowers",
                "description": "Core skills",
                "version": "6.1.1",
            },
            ".claude-plugin/marketplace.json": {
                "name": "superpowers-dev",
                "plugins": [{"name": "superpowers"}],
            },
            ".cursor-plugin/plugin.json": {
                "name": "superpowers",
                "displayName": "Superpowers",
                "description": "Core skills library",
                "version": "6.1.1",
            },
            ".codex-plugin/plugin.json": {
                "name": "superpowers",
                "description": "Codex packaging",
                "version": "6.1.1",
            },
            ".agents/plugins/marketplace.json": {
                "name": "superpowers-marketplace",
                "plugins": [{"name": "superpowers"}],
            },
            ".kimi-plugin/plugin.json": {
                "name": "superpowers",
                "description": "Kimi packaging",
            },
            "gemini-extension.json": {
                "name": "superpowers",
                "description": "Antigravity / Gemini extension",
            },
        }
        plugin = normalize_plugin(
            repository=repository,
            manifests=manifests,
            providers=[
                "claude",
                "cursor",
                "codex",
                "agents",
                "kimi",
                "opencode",
                "pi",
                "antigravity",
            ],
            directory_supports={"opencode", "pi"},
        )
        assert plugin["name"] == "superpowers"
        assert plugin["displayName"] == "Superpowers"
        assert plugin["supports"]["claude"] is True
        assert plugin["supports"]["cursor"] is True
        assert plugin["supports"]["codex"] is True
        assert plugin["supports"]["agents"] is True
        assert plugin["supports"]["kimi"] is True
        assert plugin["supports"]["opencode"] is True
        assert plugin["supports"]["pi"] is True
        assert plugin["supports"]["antigravity"] is True
        assert plugin["claude"]["marketplaceName"] == "superpowers-dev"

    def test_normalize_plugin_empty_when_no_manifests(self) -> None:
        plugin = normalize_plugin(
            repository={"name": "empty"},
            manifests={},
            providers=["claude", "cursor", "codex"],
        )
        assert plugin == {}

    def test_detect_directory_providers(self) -> None:
        from github.core.exporters.plugin_exporter.utils import (
            detect_directory_providers,
            path_touches_plugin,
        )

        found = detect_directory_providers(
            {".opencode/plugins/superpowers.js", "README.md"},
            ["opencode", "pi", "claude"],
        )
        assert found == {"opencode"}
        assert path_touches_plugin(".pi/extensions/superpowers.ts", ["pi"])
        assert not path_touches_plugin("skills/foo/SKILL.md", ["pi"])

    def test_empty_plugin_shape(self) -> None:
        from github.core.exporters.plugin_exporter.utils import empty_plugin

        plugin = empty_plugin(name="my-repo")
        assert plugin["name"] == "my-repo"
        assert plugin["displayName"] == "my-repo"
        assert all(value is False for value in plugin["supports"].values())
        assert all(plugin[provider] == {} for provider in plugin["supports"])

        named = empty_plugin(name="my-repo", display_name="My Repo")
        assert named["displayName"] == "My Repo"
