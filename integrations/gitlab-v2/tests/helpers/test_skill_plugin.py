from gitlab.helpers.skill_plugin import (
    DEFAULT_SKILL_PATHS,
    _parse_skill_markdown,
    build_skill_object,
    detect_directory_providers,
    empty_plugin,
    enrich_file_to_skill,
    matches_skill_path,
    normalize_plugin,
    path_touches_plugin,
    plugin_search_paths,
    skill_search_paths,
)


def test_default_skill_paths_cover_documented_agents() -> None:
    for root in (
        ".agents/skills",
        ".agent/skills",
        ".cursor/skills",
        ".claude/skills",
        ".codex/skills",
        ".github/skills",
        ".opencode/skills",
        "skills",
    ):
        assert any(path.startswith(f"{root}/") for path in DEFAULT_SKILL_PATHS)


def test_skill_search_paths_from_globs() -> None:
    paths = skill_search_paths(
        [
            "skills/**/SKILL.md",
            ".cursor/skills/**/SKILL.md",
            ".github/skills/**/SKILL.md",
        ]
    )
    assert "skills/*/SKILL.md" in paths
    assert "skills/*/*/SKILL.md" in paths
    assert "skills/SKILL.md" in paths
    assert ".cursor/skills/*/SKILL.md" in paths
    assert ".cursor/skills/*/*/SKILL.md" in paths
    assert ".cursor/skills/SKILL.md" in paths
    assert ".github/skills/*/SKILL.md" in paths
    assert ".github/skills/*/*/SKILL.md" in paths
    assert ".github/skills/SKILL.md" in paths
    assert "SKILL.md" in paths


def test_matches_skill_path() -> None:
    globs = [
        "skills/**/SKILL.md",
        ".cursor/skills/**/SKILL.md",
        ".github/skills/**/SKILL.md",
    ]
    assert matches_skill_path("skills/hello/SKILL.md", globs)
    assert matches_skill_path("skills/hello/skill.md", globs)
    assert matches_skill_path(".cursor/skills/a/SKILL.md", globs)
    assert matches_skill_path(".github/skills/copilot/SKILL.md", globs)
    assert not matches_skill_path("packages/ai/skills/x/SKILL.md", globs)
    assert matches_skill_path(
        "packages/ai/skills/x/SKILL.md",
        ["packages/**/SKILL.md"],
    )
    assert not matches_skill_path("README.md", globs)


def test_plugin_search_paths_include_directory_wildcards() -> None:
    paths = plugin_search_paths(["opencode", "pi", "cursor"])
    assert ".opencode/plugins/*" in paths
    assert ".pi/extensions/*" in paths
    assert ".cursor-plugin/plugin.json" in paths


def test_enrich_file_to_skill_respects_path_globs() -> None:
    entity = {
        "file": {
            "path": "packages/ai/skills/x/SKILL.md",
            "content": "---\nname: x\n---\n\n# X\n",
            "ref": "main",
        },
        "repo": {"path_with_namespace": "group/repo", "default_branch": "main"},
    }
    assert enrich_file_to_skill(entity, path_globs=["skills/**/SKILL.md"]) is None
    skill = enrich_file_to_skill(entity, path_globs=["packages/**/SKILL.md"])
    assert skill is not None
    assert skill["skill"]["skillMdPath"] == "packages/ai/skills/x/SKILL.md"
    assert skill["repo"]["path_with_namespace"] == "group/repo"
    assert skill["__branch"] == "main"
    assert "# X" in skill["skill"]["instructions"]


def test_parse_and_build_skill() -> None:
    content = """---
name: hello
description: desc
---

# Body
"""
    fm, body = _parse_skill_markdown(content)
    assert fm["name"] == "hello"
    assert "# Body" in body
    skill = build_skill_object(
        skill_md_path="skills/hello/SKILL.md",
        content=content,
        path_globs=["skills/**/SKILL.md"],
    )
    assert skill["instructions"] is not None
    assert "# Body" in skill["instructions"]
    assert skill["skillMdPath"] == "skills/hello/SKILL.md"
    assert skill["root"] == "skills"


def test_parse_skill_markdown_unclosed_frontmatter() -> None:
    fm, body = _parse_skill_markdown("---\nname: x")
    assert fm == {}
    assert body.startswith("---")


def test_normalize_plugin() -> None:
    plugin = normalize_plugin(
        repository={"name": "superpowers"},
        manifests={
            ".cursor-plugin/plugin.json": {
                "name": "superpowers",
                "displayName": "Superpowers",
                "description": "desc",
            },
            "gemini-extension.json": {"name": "superpowers"},
        },
        providers=["claude", "cursor", "codex", "antigravity", "opencode", "pi"],
        directory_supports={"opencode"},
    )
    assert plugin["displayName"] == "Superpowers"
    assert plugin["supports"]["cursor"] is True
    assert plugin["supports"]["claude"] is False
    assert plugin["supports"]["antigravity"] is True
    assert plugin["supports"]["opencode"] is True
    assert plugin["supports"]["pi"] is False


def test_plugin_directory_helpers() -> None:
    assert path_touches_plugin(".opencode/plugins/superpowers.js", ["opencode"])
    found = detect_directory_providers(
        {".pi/extensions/superpowers.ts"}, ["opencode", "pi"]
    )
    assert found == {"pi"}
    paths = plugin_search_paths(["claude", "opencode", "antigravity"])
    assert ".claude-plugin/plugin.json" in paths
    assert ".opencode/plugins/*" in paths
    assert "gemini-extension.json" in paths


def test_empty_plugin_shape() -> None:
    plugin = empty_plugin(name="my-repo")
    assert plugin["name"] == "my-repo"
    assert plugin["displayName"] == "my-repo"
    assert all(value is False for value in plugin["supports"].values())
    assert all(plugin[provider] == {} for provider in plugin["supports"])

    named = empty_plugin(name="my-repo", display_name="My Repo")
    assert named["displayName"] == "My Repo"
