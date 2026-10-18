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

# Vendored copies of a plugin are not authored plugins.
IGNORED_PATH_SEGMENTS = frozenset({"node_modules", "vendor", ".git", "dist"})

# JSON (or marketplace) files that mark a plugin root, matched as path suffixes.
PLUGIN_MANIFEST_PATHS: dict[PluginProvider, list[str]] = {
    "claude": [
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
    ],
    "cursor": [".cursor-plugin/plugin.json"],
    "codex": [".codex-plugin/plugin.json"],
    "agents": [".agents/plugins/marketplace.json"],
    "kimi": [".kimi-plugin/plugin.json"],
    # Bare filename: matches `gemini-extension.json` at any depth (blobs only).
    "antigravity": ["gemini-extension.json"],
}

# Manifests that list sibling plugins instead of describing a single plugin.
# They only add metadata to a plugin root that has the provider's primary manifest.
PLUGIN_MARKETPLACE_PATHS: dict[PluginProvider, str] = {
    "claude": ".claude-plugin/marketplace.json",
    "agents": ".agents/plugins/marketplace.json",
}

# Directory markers (non-JSON plugin packaging, e.g. superpowers). The plugin
# root is the parent of the marker directory.
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
    `path` is the plugin root: empty for the repository root.
    """

    model_config = ConfigDict(extra="allow")

    name: str
    display_name: str = Field(serialization_alias="displayName")
    description: str = ""
    version: Optional[str] = None
    path: str = ""
    supports: dict[str, bool]


class PluginRawItem(BaseModel):
    """Raw item emitted for the `plugin` kind, by both resync and webhooks."""

    plugin: Plugin
    repository: dict[str, Any] = Field(serialization_alias="__repository")
    branch: str = Field(serialization_alias="__branch")
    organization: str = Field(serialization_alias="__organization")


class _ResolvedProvider(NamedTuple):
    """Manifests found for a single provider in one plugin root."""

    primary: dict[str, Any]
    marketplace: dict[str, Any]
    document: dict[str, Any]
    is_directory_only: bool


def match_marker(
    path: str, providers: list[PluginProvider]
) -> Optional[tuple[PluginProvider, str]]:
    """Provider and plugin root for a blob path that is a plugin marker, else None."""
    if not IGNORED_PATH_SEGMENTS.isdisjoint(path.split("/")):
        return None
    padded = "/" + path  # lets a root-level marker match like a nested one
    for provider in providers:
        for marker in PLUGIN_MANIFEST_PATHS.get(provider, []):
            if padded.endswith("/" + marker):
                return provider, padded[1 : -len(marker) - 1]
        prefix = PLUGIN_DIRECTORY_PREFIXES.get(provider)
        index = padded.find("/" + prefix) if prefix else -1
        # The marker directory itself does not count, only files inside it.
        if prefix and index != -1 and len(padded) > index + 1 + len(prefix):
            return provider, padded[1:index]
    return None


def find_plugin_roots(
    blob_paths: Iterable[str],
    providers: list[PluginProvider],
    max_depth: Optional[int] = None,
) -> dict[str, dict[PluginProvider, set[str]]]:
    """Group marker paths by plugin root, then provider.

    Depth is the number of segments in the root (the repository root is 0).
    """
    roots: dict[str, dict[PluginProvider, set[str]]] = {}
    for path in blob_paths:
        match = match_marker(path, providers)
        if not match:
            continue
        provider, root = match
        if max_depth is not None and root and root.count("/") + 1 > max_depth:
            continue
        roots.setdefault(root, {}).setdefault(provider, set()).add(path)
    return roots


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
    path: str = "",
    directory_supports: Optional[set[PluginProvider]] = None,
) -> Optional[Plugin]:
    """
    Merge the provider manifests of one plugin root into a normalized plugin.

    `manifests` maps marker path relative to the root -> parsed JSON (dict).
    `path` is the plugin root (empty for the repository root).
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
            "path": path,
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

    # A marketplace file never creates a plugin on its own: marketplace-only
    # providers (agents) only annotate a root that another provider makes a plugin.
    if not any(r.primary or r.is_directory_only for r in resolved.values()):
        return {}
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

    if primary:
        return _ResolvedProvider(
            primary=primary,
            marketplace=marketplace,
            document=primary,
            is_directory_only=False,
        )

    if has_directory_marker:
        return _ResolvedProvider(
            primary={}, marketplace={}, document={}, is_directory_only=True
        )

    # A provider whose only manifest is a marketplace (agents) has no primary file.
    if marketplace and primary_path is None:
        return _ResolvedProvider(
            primary={}, marketplace=marketplace, document={}, is_directory_only=False
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
