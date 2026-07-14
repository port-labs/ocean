from __future__ import annotations

from typing import Any, Literal, Optional

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

# Directory markers (non-JSON plugin packaging, e.g. superpowers).
PLUGIN_DIRECTORY_PREFIXES: dict[PluginProvider, str] = {
    "opencode": ".opencode/plugins/",
    "pi": ".pi/extensions/",
}


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
        if normalized.startswith(prefix) or normalized.startswith(prefix.rstrip("/")):
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
        if any(path.startswith(prefix) or path == prefix.rstrip("/") for path in tree_paths):
            found.add(provider)
    return found


def path_touches_plugin(
    path: str, providers: list[PluginProvider]
) -> bool:
    """True if a changed path is a known plugin manifest or under a plugin dir."""
    return provider_for_manifest_path(path) in set(providers) or any(
        path.startswith(PLUGIN_DIRECTORY_PREFIXES[p])
        for p in providers
        if p in PLUGIN_DIRECTORY_PREFIXES
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_field(data: dict[str, Any], *keys: str) -> Optional[str]:
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
    directory_supports: Optional[set[PluginProvider]] = None,
) -> dict[str, Any]:
    """
    Merge provider manifests into a normalized plugin object.

    `manifests` maps repo-relative path -> parsed JSON (dict).
    `directory_supports` marks providers detected via directory markers only.
    """
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

    marketplace_name = _str_field(claude_marketplace, "name") or _str_field(
        agents_marketplace, "name"
    )
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
    repo_name = repository.get("name") or ""

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

    claude_block: dict[str, Any] = {}
    if supports["claude"]:
        claude_block = {
            **claude_plugin,
            "name": claude_name or name,
            "marketplaceName": marketplace_name
            if marketplace_name and claude_marketplace
            else _str_field(claude_marketplace, "name"),
            "marketplace": claude_marketplace or None,
        }

    agents_block: dict[str, Any] = {}
    if supports["agents"]:
        agents_block = {
            **agents_marketplace,
            "name": agents_plugin_name or name,
            "marketplaceName": _str_field(agents_marketplace, "name"),
        }

    return {
        "name": name,
        "displayName": display_name,
        "description": description,
        "version": version,
        "supports": supports,
        "claude": claude_block if supports["claude"] else {},
        "cursor": cursor_plugin if supports["cursor"] else {},
        "codex": codex_plugin if supports["codex"] else {},
        "agents": agents_block if supports["agents"] else {},
        "kimi": kimi_plugin if supports["kimi"] else {},
        "opencode": {"detected": True} if supports["opencode"] else {},
        "pi": {"detected": True} if supports["pi"] else {},
        "antigravity": antigravity_ext if supports["antigravity"] else {},
    }


def build_plugin_raw_item(
    *,
    repository: dict[str, Any],
    manifests: dict[str, Any],
    providers: list[PluginProvider],
    branch: Optional[str] = None,
    organization: Optional[str] = None,
    directory_supports: Optional[set[PluginProvider]] = None,
) -> Optional[dict[str, Any]]:
    plugin = normalize_plugin(
        repository=repository,
        manifests=manifests,
        providers=providers,
        directory_supports=directory_supports,
    )
    if not plugin:
        return None
    item: dict[str, Any] = {
        "plugin": plugin,
        "repository": repository,
    }
    if branch is not None:
        item["branch"] = branch
    if organization is not None:
        item["organization"] = organization
    return item
