from gitlab.helpers.skill_plugin import (
    DEFAULT_SKILL_ROOTS,
    build_skill_object,
    detect_directory_providers,
    enrich_file_to_skill,
    matches_skill_path,
    normalize_plugin,
    parse_skill_markdown,
    path_touches_plugin,
    plugin_search_paths,
    skill_search_paths,
)


def test_default_skill_roots_cover_documented_agents() -> None:
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
        assert root in DEFAULT_SKILL_ROOTS


def test_skill_search_paths() -> None:
    paths = skill_search_paths(["skills", ".cursor/skills", ".github/skills"])
    assert "skills/*/SKILL.md" in paths
    assert "skills/SKILL.md" in paths
    assert ".cursor/skills/*/SKILL.md" in paths
    assert ".cursor/skills/SKILL.md" in paths
    assert ".github/skills/*/SKILL.md" in paths
    assert ".github/skills/SKILL.md" in paths
    assert "SKILL.md" in paths


def test_matches_skill_path() -> None:
    roots = ["skills", ".cursor/skills", ".github/skills"]
    assert matches_skill_path("skills/hello/SKILL.md", roots, [])
    assert matches_skill_path("skills/hello/skill.md", roots, [])
    assert matches_skill_path(".cursor/skills/a/SKILL.md", roots, [])
    assert matches_skill_path(".github/skills/copilot/SKILL.md", roots, [])
    # Broad nested "skills" segment is no longer accepted — use selector.paths
    assert not matches_skill_path("packages/ai/skills/x/SKILL.md", roots, [])
    assert matches_skill_path(
        "packages/ai/skills/x/SKILL.md",
        roots,
        ["packages/**/SKILL.md"],
    )
    assert not matches_skill_path("README.md", roots, [])


def test_plugin_search_paths_include_directory_wildcards() -> None:
    paths = plugin_search_paths(["opencode", "pi", "cursor"])
    assert ".opencode/plugins/*" in paths
    assert ".pi/extensions/*" in paths
    assert ".cursor-plugin/plugin.json" in paths


def test_enrich_file_to_skill_respects_extra_paths() -> None:
    entity = {
        "file": {
            "path": "packages/ai/skills/x/SKILL.md",
            "content": "---\nname: x\n---\n\n# X\n",
            "ref": "main",
        },
        "repo": {"path_with_namespace": "group/repo", "default_branch": "main"},
    }
    assert (
        enrich_file_to_skill(
            entity, content_mode="skill.md", roots=["skills"], extra_paths=[]
        )
        is None
    )
    skill = enrich_file_to_skill(
        entity,
        content_mode="skill.md",
        roots=["skills"],
        extra_paths=["packages/**/SKILL.md"],
    )
    assert skill is not None
    assert skill["skill"]["skillMdPath"] == "packages/ai/skills/x/SKILL.md"


def test_parse_and_build_skill() -> None:
    content = """---
name: hello
description: desc
---

# Body
"""
    fm, body = parse_skill_markdown(content)
    assert fm["name"] == "hello"
    skill = build_skill_object(
        skill_md_path="skills/hello/SKILL.md",
        content=content,
        content_mode="skill.md",
        roots=["skills"],
    )
    assert skill["instructions"] is not None
    assert "# Body" in skill["instructions"]
    assert skill["skillMdPath"] == "skills/hello/SKILL.md"


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
