from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Literal, NamedTuple

from loguru import logger
from wcmatch import glob
from yaml import safe_load

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

DEFAULT_SKILL_PATHS: list[str] = [
    ".agents/skills/**/SKILL.md",
    ".agent/skills/**/SKILL.md",
    ".cursor/skills/**/SKILL.md",
    ".claude/skills/**/SKILL.md",
    ".codex/skills/**/SKILL.md",
    ".github/skills/**/SKILL.md",
    ".opencode/skills/**/SKILL.md",
    "skills/**/SKILL.md",
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

# Manifests that list sibling plugins instead of describing a single plugin.
PLUGIN_MARKETPLACE_PATHS: dict[PluginProvider, str] = {
    "claude": ".claude-plugin/marketplace.json",
    "agents": ".agents/plugins/marketplace.json",
}

PLUGIN_DIRECTORY_PREFIXES: dict[PluginProvider, str] = {
    "opencode": ".opencode/plugins/",
    "pi": ".pi/extensions/",
}

# Search paths for directory-only plugin packaging.
# Trailing /* discovers any file directly under the directory.
PLUGIN_DIRECTORY_SEARCH_PATHS: dict[PluginProvider, str] = {
    "opencode": ".opencode/plugins/*",
    "pi": ".pi/extensions/*",
}

# Order in which provider manifests win when resolving shared plugin fields.
PLUGIN_FIELD_PRECEDENCE: list[PluginProvider] = [
    "cursor",
    "claude",
    "codex",
    "kimi",
    "antigravity",
    "agents",
    "opencode",
    "pi",
]


class _ResolvedProvider(NamedTuple):
    """Manifests found for a single provider in one repository."""

    primary: dict[str, Any]
    marketplace: dict[str, Any]
    document: dict[str, Any]
    is_directory_only: bool


_GLOB_FLAGS = glob.GLOBSTAR | glob.DOTGLOB | glob.IGNORECASE


def _glob_root(pattern: str) -> str:
    """Strip the SKILL.md suffix from a glob to get the configured root prefix."""
    cleaned = pattern.strip("/")
    suffixes = (
        f"/**/{SKILL_MD_FILENAME}",
        f"/{SKILL_MD_FILENAME}",
        f"**/{SKILL_MD_FILENAME}",
        SKILL_MD_FILENAME,
    )
    lower = cleaned.lower()
    for suffix in suffixes:
        if lower.endswith(suffix.lower()):
            return cleaned[: -len(suffix)].strip("/")
    return cleaned


def matches_skill_path(path: str, path_globs: list[str]) -> bool:
    normalized = path.strip("/")
    if Path(normalized).name.lower() != SKILL_MD_FILENAME.lower():
        return False
    return any(
        glob.globmatch(normalized, pattern.strip("/"), flags=_GLOB_FLAGS)
        for pattern in path_globs
    )


def infer_skill_root(skill_md_path: str, path_globs: list[str]) -> str:
    """Root that matched this SKILL.md, for mapping filters."""
    normalized = skill_md_path.strip("/")
    for pattern in path_globs:
        if glob.globmatch(normalized, pattern.strip("/"), flags=_GLOB_FLAGS):
            root = _glob_root(pattern)
            if root:
                return root
    skill_dir = str(Path(normalized).parent).replace("\\", "/")
    parent = str(Path(skill_dir).parent).replace("\\", "/")
    return parent if parent not in (".", "") else skill_dir


def _parse_skill_markdown(content: str) -> tuple[dict[str, Any], str]:
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
    path_globs: list[str],
) -> dict[str, Any]:
    frontmatter, body = _parse_skill_markdown(content)
    path_obj = Path(skill_md_path)
    skill_dir = str(path_obj.parent).replace("\\", "/")
    path_name = path_obj.parent.name

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        name = path_name

    description = frontmatter.get("description")
    if not isinstance(description, str):
        description = ""

    return {
        "name": name,
        "description": description,
        "instructions": body,
        "frontmatter": frontmatter,
        "path": skill_dir,
        "skillMdPath": skill_md_path,
        "root": infer_skill_root(skill_md_path, path_globs),
    }


def build_skill_delete_stub(
    *,
    skill_md_path: str,
    path_globs: list[str],
) -> dict[str, Any]:
    """Skill shape for deletes, where the file content is no longer available."""
    path_obj = Path(skill_md_path)
    return {
        "name": path_obj.parent.name,
        "description": "",
        "instructions": None,
        "frontmatter": {},
        "path": str(path_obj.parent).replace("\\", "/"),
        "skillMdPath": skill_md_path,
        "root": infer_skill_root(skill_md_path, path_globs),
    }


def enrich_file_to_skill(
    file_entity: dict[str, Any],
    *,
    path_globs: list[str],
) -> dict[str, Any] | None:
    """Convert GitLab `{file, repo}` enrichment into normalized skill raw item."""
    file_data = file_entity.get("file") or {}
    repo = file_entity.get("repo") or {}
    path = file_data.get("path") or file_data.get("file_path") or ""
    content = file_data.get("content")
    if not isinstance(content, str):
        return None
    if not matches_skill_path(path, path_globs):
        return None

    return {
        "skill": build_skill_object(
            skill_md_path=path,
            content=content,
            path_globs=path_globs,
        ),
        "repo": repo,
        "__branch": file_data.get("ref") or repo.get("default_branch") or "main",
    }


def empty_plugin(*, name: str, display_name: str | None = None) -> dict[str, Any]:
    """Shape of a plugin with no manifests left, used for webhook-driven deletes."""
    return {
        "name": name,
        "displayName": display_name or name,
        "description": "",
        "version": None,
        "supports": {provider: False for provider in DEFAULT_PLUGIN_PROVIDERS},
        **{provider: {} for provider in DEFAULT_PLUGIN_PROVIDERS},
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
    """Exact manifest paths plus directory globs to discover per project."""
    paths = all_manifest_paths(providers)
    for provider in providers:
        search = PLUGIN_DIRECTORY_SEARCH_PATHS.get(provider)
        if search:
            paths.append(search)
    return paths


def normalize_plugin(
    *,
    repository: dict[str, Any],
    manifests: dict[str, Any],
    providers: list[PluginProvider],
    directory_supports: set[PluginProvider] | None = None,
) -> dict[str, Any]:
    """Merge provider manifests into a normalized plugin dict.

    Iterates configured providers via shared manifest/dir maps so adding a
    packaging format is data, not another branch in this function.
    """
    resolved = _resolve_providers(manifests, providers, directory_supports or set())
    if not resolved:
        return {}

    repo_name = repository.get("name") or repository.get("path") or ""
    name = _first(_str_field(r.primary, "name") for r in resolved.values()) or repo_name
    display_name = _first(_display_name(r) for r in resolved.values()) or name
    description = (
        _first(_str_field(r.primary, "description") for r in resolved.values())
        or _first(_str_field(r.marketplace, "description") for r in resolved.values())
        or ""
    )

    documents: dict[str, Any] = {provider: {} for provider in DEFAULT_PLUGIN_PROVIDERS}
    for provider, provider_manifests in resolved.items():
        documents[provider] = _provider_document(provider_manifests, name)

    return {
        "name": name,
        "displayName": display_name,
        "description": description,
        "version": _first(_str_field(r.primary, "version") for r in resolved.values()),
        "supports": {
            provider: provider in resolved for provider in DEFAULT_PLUGIN_PROVIDERS
        },
        **documents,
    }


def _resolve_providers(
    manifests: dict[str, Any],
    providers: list[PluginProvider],
    directory_supports: set[PluginProvider],
) -> dict[PluginProvider, _ResolvedProvider]:
    """Resolve every requested provider, ordered by field precedence."""
    ordered = [
        provider for provider in PLUGIN_FIELD_PRECEDENCE if provider in providers
    ] + [provider for provider in providers if provider not in PLUGIN_FIELD_PRECEDENCE]

    resolved: dict[PluginProvider, _ResolvedProvider] = {}
    for provider in ordered:
        provider_manifests = _resolve_provider(
            provider, manifests, provider in directory_supports
        )
        if provider_manifests:
            resolved[provider] = provider_manifests
    return resolved


def _resolve_provider(
    provider: PluginProvider,
    manifests: dict[str, Any],
    has_directory_marker: bool,
) -> _ResolvedProvider | None:
    marketplace_path = PLUGIN_MARKETPLACE_PATHS.get(provider)
    primary_path = next(
        (
            path
            for path in PLUGIN_MANIFEST_PATHS.get(provider, [])
            if path != marketplace_path
        ),
        None,
    )

    primary = _as_dict(manifests.get(primary_path)) if primary_path else {}
    marketplace = _as_dict(manifests.get(marketplace_path)) if marketplace_path else {}

    # A marketplace-only repo still describes a plugin through its first entry.
    if not primary and marketplace:
        entries = [
            entry
            for entry in marketplace.get("plugins") or []
            if isinstance(entry, dict)
        ]
        primary = entries[0] if entries else {}

    if primary or marketplace:
        return _ResolvedProvider(
            primary=primary,
            marketplace=marketplace,
            document=primary if primary_path else marketplace,
            is_directory_only=False,
        )

    if has_directory_marker:
        return _ResolvedProvider(
            primary={}, marketplace={}, document={}, is_directory_only=True
        )

    return None


def _provider_document(
    provider_manifests: _ResolvedProvider, plugin_name: str
) -> dict[str, Any]:
    if provider_manifests.is_directory_only:
        return {"detected": True}
    if not provider_manifests.marketplace:
        return dict(provider_manifests.document)
    return {
        **provider_manifests.document,
        "name": _str_field(provider_manifests.primary, "name") or plugin_name,
        "marketplaceName": _str_field(provider_manifests.marketplace, "name"),
    }


def _display_name(provider_manifests: _ResolvedProvider) -> str | None:
    return _str_field(
        provider_manifests.primary, "displayName", "display_name"
    ) or _str_field(
        _as_dict(provider_manifests.marketplace.get("interface")),
        "displayName",
        "display_name",
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_field(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return None


def _first(values: Iterable[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None
