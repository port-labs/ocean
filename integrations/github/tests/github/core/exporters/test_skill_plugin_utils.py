from github.core.exporters.skill_exporter.utils import (
    build_skill_object,
    infer_skill_root,
    matches_skill_path,
    _parse_skill_markdown,
)
from github.core.exporters.plugin_exporter.utils import normalize_plugin


class TestSkillUtils:
    def test_infer_skill_root(self) -> None:
        globs = [".cursor/skills/**/SKILL.md", "skills/**/SKILL.md"]
        assert (
            infer_skill_root(".cursor/skills/ponytail/SKILL.md", globs)
            == ".cursor/skills"
        )
        assert infer_skill_root("skills/hello/SKILL.md", globs) == "skills"

    def test_matches_skill_path(self) -> None:
        globs = ["skills/**/SKILL.md", "packages/**/SKILL.md"]
        assert matches_skill_path("skills/hello/SKILL.md", globs)
        assert matches_skill_path("packages/ai/skills/x/SKILL.md", globs)
        assert matches_skill_path(".cursor/skills/x/SKILL.md", [".cursor/**/SKILL.md"])
        assert not matches_skill_path("packages/ai/skills/x/SKILL.md", ["skills/**/SKILL.md"])

    def test_build_skill_object_multi_segment_root(self) -> None:
        skill = build_skill_object(
            skill_md_path=".cursor/skills/hello/SKILL.md",
            content="# Hello",
            path_globs=[".cursor/skills/**/SKILL.md"],
        )
        assert skill["root"] == ".cursor/skills"
        assert skill["path"] == ".cursor/skills/hello"
        assert skill["instructions"] == "# Hello"

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

    def test_build_skill_object_always_includes_body(self) -> None:
        content = """---
name: hello-skill
description: A minimal example
---

# Hello
"""
        skill = build_skill_object(
            skill_md_path="skills/hello-skill/SKILL.md",
            content=content,
            path_globs=["skills/**/SKILL.md"],
        )
        assert skill["name"] == "hello-skill"
        assert skill["description"] == "A minimal example"
        assert skill["instructions"] is not None
        assert "# Hello" in skill["instructions"]
        assert skill["path"] == "skills/hello-skill"
        assert skill["skillMdPath"] == "skills/hello-skill/SKILL.md"
        assert skill["root"] == "skills"

    def test_build_skill_object_name_fallback(self) -> None:
        skill = build_skill_object(
            skill_md_path="skills/my-skill/SKILL.md",
            content="# No frontmatter",
            path_globs=["skills/**/SKILL.md"],
        )
        assert skill["name"] == "my-skill"
        assert skill["description"] == ""


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
        assert plugin["name"] == "superpowers"
        assert plugin["supports"]["claude"] is True
        assert plugin["supports"]["cursor"] is True
        assert plugin["supports"]["codex"] is False
        assert plugin["claude"]["marketplaceName"] == "superpowers-dev"

    def test_normalize_plugin_directory_only(self) -> None:
        repository = {"name": "opencode-plugin", "full_name": "acme/opencode-plugin"}
        plugin = normalize_plugin(
            repository=repository,
            manifests={},
            providers=["opencode", "pi"],
            directory_supports={"opencode"},
        )
        assert plugin is not None
        assert plugin["supports"]["opencode"] is True
        assert plugin["supports"]["pi"] is False
