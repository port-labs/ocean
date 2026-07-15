from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from loguru import logger
from yaml import safe_load

SkillContentMode = Literal["frontmatter", "skill.md"]
PluginProvider = Literal[
    "claude",
    "cursor",
    "codex",
    "agents",
    "kimi",
    "opencode",
    "pi",
    "antigravity",
]

DEFAULT_SKILL_ROOTS: list[str] = [
    ".agents/skills",
    ".agent/skills",
    ".cursor/skills",
    ".claude/skills",
    ".codex/skills",
    ".github/skills",
    ".opencode/skills",
    "skills",
]

SKILL_MD_FILENAME = "SKILL.md"

DEFAULT_PLUGIN_PROVIDERS: list[PluginProvider] = [
    "claude",
    "cursor",
    "codex",
    "agents",
    "kimi",
    "opencode",
    "pi",
    "antigravity",
]

PLUGIN_MANIFEST_PATHS: dict[PluginProvider, list[str]] = {
    "claude": [
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
    ],
    "cursor": [".cursor-plugin/plugin.json"],
    "codex": [".codex-plugin/plugin.json"],
    "agents": [".agents/plugins/marketplace.json"],
    "kimi": [".kimi-plugin/plugin.json"],
    "antigravity": ["gemini-extension.json"],
}

PLUGIN_DIRECTORY_PREFIXES: dict[PluginProvider, str] = {
    "opencode": ".opencode/plugins/",
    "pi": ".pi/extensions/",
}

# GitLab search paths for directory-only plugin packaging.
PLUGIN_DIRECTORY_SEARCH_PATHS: dict[PluginProvider, str] = {
    "opencode": ".opencode/plugins/*",
    "pi": ".pi/extensions/*",
}


def skill_search_paths(roots: list[str]) -> list[str]:
    """Paths suitable for GitLab Advanced Search (no ** globs)."""
    paths: list[str] = []
    for root in roots:
        clean = root.strip().strip("/")
        if clean:
            # Search under the root directory for SKILL.md files
            paths.append(f"{clean}/{SKILL_MD_FILENAME}")
    # Broad fallback for nested */skills/*/SKILL.md layouts
    paths.append(SKILL_MD_FILENAME)
    return paths


def matches_skill_path(path: str, roots: list[str], extra_paths: list[str]) -> bool:
    normalized = path.strip("/")
    if not normalized.endswith(SKILL_MD_FILENAME):
        return False

    for root in roots:
        clean = root.strip().strip("/")
        if normalized == f"{clean}/{SKILL_MD_FILENAME}":
            return True
        if normalized.startswith(f"{clean}/") and normalized.endswith(
            f"/{SKILL_MD_FILENAME}"
        ):
            return True

    for pattern in extra_paths:
        if _simple_match(normalized, pattern):
            return True

    return False


def _simple_match(path: str, pattern: str) -> bool:
    import fnmatch

    return fnmatch.fnmatch(path, pattern.strip("/"))


def match_skill_root(skill_md_path: str, roots: list[str]) -> str | None:
    normalized = skill_md_path.strip("/")
    for root in roots:
        clean = root.strip().strip("/")
        if normalized == f"{clean}/{SKILL_MD_FILENAME}":
            return clean
        if normalized.startswith(f"{clean}/") and normalized.endswith(
            f"/{SKILL_MD_FILENAME}"
        ):
            return clean
    return None


def parse_skill_markdown(content: str) -> tuple[dict[str, Any], str]:
    text = content.replace("\r\n", "\n")
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    raw_fm = parts[1].strip()
    body = parts[2].lstrip("\n")
    if not raw_fm:
        return {}, body

    try:
        parsed = safe_load(raw_fm)
        if isinstance(parsed, dict):
            return parsed, body
        return {}, body
    except Exception as exc:
        logger.warning(f"Failed to parse skill frontmatter: {exc}")
        return {}, body


def build_skill_object(
    *,
    skill_md_path: str,
    content: str,
    content_mode: SkillContentMode,
    roots: list[str] | None = None,
) -> dict[str, Any]:
    roots = roots or DEFAULT_SKILL_ROOTS
    frontmatter, body = parse_skill_markdown(content)
    path_obj = Path(skill_md_path)
    skill_dir = str(path_obj.parent).replace("\\", "/")
    path_name = path_obj.parent.name

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        name = path_name

    description = frontmatter.get("description")
    if not isinstance(description, str):
        description = ""

    root = match_skill_root(skill_md_path, roots) or (
        skill_dir.split("/")[0] if skill_dir else ""
    )

    skill: dict[str, Any] = {
        "name": name,
        "description": description,
        "instructions": None,
        "frontmatter": frontmatter,
        "path": skill_dir,
        "skillMdPath": skill_md_path,
        "root": root,
    }
    if content_mode == "skill.md":
        skill["instructions"] = body
    return skill


def enrich_file_to_skill(
    file_entity: dict[str, Any],
    *,
    content_mode: SkillContentMode,
    roots: list[str],
    extra_paths: list[str] | None = None,
) -> dict[str, Any] | None:
    """Convert GitLab `{file, repo}` enrichment into normalized skill raw item."""
    file_data = file_entity.get("file") or {}
    repo = file_entity.get("repo") or {}
    path = file_data.get("path") or file_data.get("file_path") or ""
    content = file_data.get("content")
    if not isinstance(content, str):
        return None
    if not matches_skill_path(path, roots, extra_paths or []):
        return None

    return {
        "skill": build_skill_object(
            skill_md_path=path,
            content=content,
            content_mode=content_mode,
            roots=roots,
        ),
        "repository": repo,
        "branch": file_data.get("ref") or repo.get("default_branch") or "main",
    }


def all_manifest_paths(providers: list[PluginProvider]) -> list[str]:
    paths: list[str] = []
    for provider in providers:
        paths.extend(PLUGIN_MANIFEST_PATHS.get(provider, []))
    return paths


def provider_for_manifest_path(path: str) -> PluginProvider | None:
    normalized = path.strip("/")
    for provider, manifests in PLUGIN_MANIFEST_PATHS.items():
        if normalized in manifests:
            return provider
    for provider, prefix in PLUGIN_DIRECTORY_PREFIXES.items():
        if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
            return provider
    return None


def detect_directory_providers(
    paths: set[str], providers: list[PluginProvider]
) -> set[PluginProvider]:
    found: set[PluginProvider] = set()
    for provider in providers:
        prefix = PLUGIN_DIRECTORY_PREFIXES.get(provider)
        if not prefix:
            continue
        bare = prefix.rstrip("/")
        if any(path == bare or path.startswith(prefix) for path in paths):
            found.add(provider)
    return found


def path_touches_plugin(path: str, providers: list[PluginProvider]) -> bool:
    provider = provider_for_manifest_path(path)
    return provider is not None and provider in providers


def plugin_search_paths(providers: list[PluginProvider]) -> list[str]:
    """Exact manifests plus directory globs for GitLab Advanced Search."""
    paths = all_manifest_paths(providers)
    for provider in providers:
        search = PLUGIN_DIRECTORY_SEARCH_PATHS.get(provider)
        if search:
            paths.append(search)
    return paths


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_field(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return None


def normalize_plugin(
    *,
    repository: dict[str, Any],
    manifests: dict[str, Any],
    providers: list[PluginProvider],
    directory_supports: set[PluginProvider] | None = None,
) -> dict[str, Any]:
    directory_supports = directory_supports or set()

    claude_plugin = _as_dict(manifests.get(".claude-plugin/plugin.json"))
    claude_marketplace = _as_dict(manifests.get(".claude-plugin/marketplace.json"))
    cursor_plugin = _as_dict(manifests.get(".cursor-plugin/plugin.json"))
    codex_plugin = _as_dict(manifests.get(".codex-plugin/plugin.json"))
    agents_marketplace = _as_dict(manifests.get(".agents/plugins/marketplace.json"))
    kimi_plugin = _as_dict(manifests.get(".kimi-plugin/plugin.json"))
    antigravity_ext = _as_dict(manifests.get("gemini-extension.json"))

    supports = {
        "claude": bool(claude_plugin or claude_marketplace) and "claude" in providers,
        "cursor": bool(cursor_plugin) and "cursor" in providers,
        "codex": bool(codex_plugin) and "codex" in providers,
        "agents": bool(agents_marketplace) and "agents" in providers,
        "kimi": bool(kimi_plugin) and "kimi" in providers,
        "opencode": ("opencode" in directory_supports) and "opencode" in providers,
        "pi": ("pi" in directory_supports) and "pi" in providers,
        "antigravity": bool(antigravity_ext) and "antigravity" in providers,
    }
    if not any(supports.values()):
        return {}

    marketplace_plugins = claude_marketplace.get("plugins")
    if isinstance(marketplace_plugins, list) and marketplace_plugins:
        first = marketplace_plugins[0]
        if isinstance(first, dict) and not claude_plugin:
            claude_plugin = first

    agents_plugins = agents_marketplace.get("plugins")
    agents_plugin_name = None
    if isinstance(agents_plugins, list) and agents_plugins:
        first_agent = agents_plugins[0]
        if isinstance(first_agent, dict):
            agents_plugin_name = _str_field(first_agent, "name")

    claude_name = _str_field(claude_plugin, "name")
    cursor_name = _str_field(cursor_plugin, "name")
    cursor_display = _str_field(cursor_plugin, "displayName", "display_name")
    codex_name = _str_field(codex_plugin, "name")
    kimi_name = _str_field(kimi_plugin, "name")
    antigravity_name = _str_field(antigravity_ext, "name")
    agents_display = None
    agents_interface = agents_marketplace.get("interface")
    if isinstance(agents_interface, dict):
        agents_display = _str_field(agents_interface, "displayName", "display_name")
    repo_name = repository.get("name") or repository.get("path") or ""

    name = (
        cursor_name
        or claude_name
        or codex_name
        or kimi_name
        or antigravity_name
        or agents_plugin_name
        or repo_name
    )
    display_name = cursor_display or agents_display or name
    description = (
        _str_field(cursor_plugin, "description")
        or _str_field(claude_plugin, "description")
        or _str_field(codex_plugin, "description")
        or _str_field(kimi_plugin, "description")
        or _str_field(antigravity_ext, "description")
        or _str_field(claude_marketplace, "description")
        or ""
    )
    version = (
        _str_field(cursor_plugin, "version")
        or _str_field(claude_plugin, "version")
        or _str_field(codex_plugin, "version")
        or _str_field(kimi_plugin, "version")
        or _str_field(antigravity_ext, "version")
    )

    return {
        "name": name,
        "displayName": display_name,
        "description": description,
        "version": version,
        "supports": supports,
        "claude": (
            {
                **claude_plugin,
                "name": claude_name or name,
                "marketplaceName": _str_field(claude_marketplace, "name"),
            }
            if supports["claude"]
            else {}
        ),
        "cursor": cursor_plugin if supports["cursor"] else {},
        "codex": codex_plugin if supports["codex"] else {},
        "agents": (
            {
                **agents_marketplace,
                "name": agents_plugin_name or name,
                "marketplaceName": _str_field(agents_marketplace, "name"),
            }
            if supports["agents"]
            else {}
        ),
        "kimi": kimi_plugin if supports["kimi"] else {},
        "opencode": {"detected": True} if supports["opencode"] else {},
        "pi": {"detected": True} if supports["pi"] else {},
        "antigravity": antigravity_ext if supports["antigravity"] else {},
    }
