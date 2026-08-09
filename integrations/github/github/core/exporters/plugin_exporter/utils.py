from __future__ import annotations

from typing import Any, Iterable, Literal, NamedTuple, Optional

from pydantic import BaseModel, ConfigDict, Field

# Providers observed in obra/superpowers and common agent plugin layouts.
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

# Exact JSON (or marketplace) files to fetch and parse.
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

# Directory markers (non-JSON plugin packaging, e.g. superpowers).
PLUGIN_DIRECTORY_PREFIXES: dict[PluginProvider, str] = {
    "opencode": ".opencode/plugins/",
    "pi": ".pi/extensions/",
}

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

# Order in which provider manifests win when resolving the shared plugin fields
# (name, display name, description, version).
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


class Plugin(BaseModel):
    """Normalized agent plugin package.

    Each detected provider is exposed as an extra top-level key holding its own
    manifest document, so adding a provider does not change this model.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    display_name: str = Field(serialization_alias="displayName")
    description: str = ""
    version: Optional[str] = None
    supports: dict[str, bool]


class PluginRawItem(BaseModel):
    """Raw item emitted for the `plugin` kind, by both resync and webhooks."""

    plugin: Plugin
    repository: dict[str, Any] = Field(serialization_alias="__repository")
    branch: str = Field(serialization_alias="__branch")
    organization: str = Field(serialization_alias="__organization")


class _ResolvedProvider(NamedTuple):
    """Manifests found for a single provider in one repository."""

    primary: dict[str, Any]
    marketplace: dict[str, Any]
    document: dict[str, Any]
    is_directory_only: bool


def all_manifest_paths(providers: list[PluginProvider]) -> list[str]:
    paths: list[str] = []
    for provider in providers:
        paths.extend(PLUGIN_MANIFEST_PATHS.get(provider, []))
    return paths


def provider_for_manifest_path(path: str) -> Optional[PluginProvider]:
    normalized = path.strip("/")
    for provider, manifests in PLUGIN_MANIFEST_PATHS.items():
        if normalized in manifests:
            return provider
    for provider, prefix in PLUGIN_DIRECTORY_PREFIXES.items():
        if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
            return provider
    return None


def detect_directory_providers(
    tree_paths: set[str], providers: list[PluginProvider]
) -> set[PluginProvider]:
    found: set[PluginProvider] = set()
    for provider in providers:
        prefix = PLUGIN_DIRECTORY_PREFIXES.get(provider)
        if not prefix:
            continue
        bare = prefix.rstrip("/")
        if any(path == bare or path.startswith(prefix) for path in tree_paths):
            found.add(provider)
    return found


def path_touches_plugin(path: str, providers: list[PluginProvider]) -> bool:
    """True if a changed path is a known plugin manifest or under a plugin dir."""
    provider = provider_for_manifest_path(path)
    return provider is not None and provider in providers


def empty_plugin(*, name: str, display_name: Optional[str] = None) -> Plugin:
    """Shape of a plugin with no manifests left, used for webhook-driven deletes."""
    return Plugin.model_validate(
        {
            "name": name,
            "display_name": display_name or name,
            "supports": {provider: False for provider in DEFAULT_PLUGIN_PROVIDERS},
            **{provider: {} for provider in DEFAULT_PLUGIN_PROVIDERS},
        }
    )


def build_plugin_raw_item(
    *,
    plugin: Plugin,
    repository: dict[str, Any],
    branch: str,
    organization: str,
) -> dict[str, Any]:
    """Single entry point for building a plugin raw item."""
    return PluginRawItem(
        plugin=plugin,
        repository=repository,
        branch=branch,
        organization=organization,
    ).model_dump(by_alias=True)


def normalize_plugin(
    *,
    repository: dict[str, Any],
    manifests: dict[str, Any],
    providers: list[PluginProvider],
    directory_supports: Optional[set[PluginProvider]] = None,
) -> Optional[Plugin]:
    """
    Merge provider manifests into a normalized plugin.

    `manifests` maps repo-relative path -> parsed JSON (dict).
    `directory_supports` marks providers detected via directory markers only.
    """
    resolved = _resolve_providers(manifests, providers, directory_supports or set())
    if not resolved:
        return None

    repo_name = repository.get("name") or ""
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

    return Plugin.model_validate(
        {
            "name": name,
            "display_name": display_name,
            "description": description,
            "version": _first(
                _str_field(r.primary, "version") for r in resolved.values()
            ),
            "supports": {
                provider: provider in resolved for provider in DEFAULT_PLUGIN_PROVIDERS
            },
            **documents,
        }
    )


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
) -> Optional[_ResolvedProvider]:
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


def _display_name(provider_manifests: _ResolvedProvider) -> Optional[str]:
    return _str_field(
        provider_manifests.primary, "displayName", "display_name"
    ) or _str_field(
        _as_dict(provider_manifests.marketplace.get("interface")),
        "displayName",
        "display_name",
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_field(data: dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return None


def _first(values: Iterable[Optional[str]]) -> Optional[str]:
    return next((value for value in values if value), None)
