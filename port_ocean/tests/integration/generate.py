"""Generate integration test file from discovery.json.

Reads `.port/resources/discovery.json` (produced by `make test/discover`),
groups third-party HTTP requests into URL patterns, and writes a ready-to-use
`tests/test_integration_resync.py` with mocked routes and a basic smoke test.

Usage (from an integration directory):
    python -m port_ocean.tests.integration.generate
"""

import json
import re
import sys
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


# -- Sensitive data detection -------------------------------------------------

_SENSITIVE_PATTERNS = re.compile(
    r"(token|secret|key|password|credential|auth|private)",
    re.IGNORECASE,
)

# Max unique values at a segment position before it becomes a wildcard.
# Positions with fewer unique values cause the group to split into subgroups.
_SPLIT_THRESHOLD = 3


def _is_sensitive_key(key: str) -> bool:
    """Check if a config key name looks like it holds sensitive data."""
    return bool(_SENSITIVE_PATTERNS.search(key))


def _sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Replace sensitive-looking values in integration config with placeholders."""
    sanitized: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, dict):
            sanitized[key] = _sanitize_config(value)
        elif _is_sensitive_key(key):
            sanitized[key] = "test-value"
        else:
            sanitized[key] = value
    return sanitized


# -- Response truncation ------------------------------------------------------


def _truncate_arrays(obj: Any, max_items: int = 2) -> Any:
    """Recursively truncate arrays in a JSON-like object to max_items."""
    if isinstance(obj, list):
        return [_truncate_arrays(item, max_items) for item in obj[:max_items]]
    elif isinstance(obj, dict):
        return {k: _truncate_arrays(v, max_items) for k, v in obj.items()}
    return obj


# -- URL pattern detection ----------------------------------------------------


def _parse_request(req: dict[str, Any]) -> tuple[str, str, list[str]]:
    """Parse a request dict into (method, base_url, path_segments)."""
    method = req["method"]
    parsed = urlparse(req["url"])
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    segments = [s for s in parsed.path.split("/") if s]
    return method, base_url, segments


def _compute_url_patterns(
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group requests by URL pattern and pick representative responses.

    Algorithm:
    1. Parse each URL into (method, base_url, path_segments)
    2. Group by (method, base_url, number_of_segments)
    3. Recursively split groups: if a segment position has few (<=3) distinct
       values, split into subgroups. Otherwise, replace with [^/]+ wildcard.
    4. Pick the first 2xx response as representative, fall back to any
    5. Order: fewer wildcards first (specific before catch-all)
    """
    # Group by (method, base_url, segment_count)
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for req in requests:
        method, base_url, segments = _parse_request(req)
        groups[(method, base_url, len(segments))].append(req)

    patterns: list[dict[str, Any]] = []

    for (method, base_url, seg_count), group_reqs in groups.items():
        if seg_count == 0:
            rep = _pick_representative(group_reqs)
            patterns.append(
                {
                    "method": method,
                    "url_pattern": "/",
                    "is_regex": False,
                    "wildcard_count": 0,
                    "response": _build_response_dict(rep),
                }
            )
            continue

        # Use recursive splitting to handle structurally different URLs
        sub_patterns = _split_and_build_patterns(method, group_reqs, seg_count)
        patterns.extend(sub_patterns)

    # Sort: fewer wildcards first (specific routes before catch-alls)
    patterns.sort(key=lambda p: (p["wildcard_count"], p["url_pattern"]))

    return patterns


def _split_and_build_patterns(
    method: str,
    requests: list[dict[str, Any]],
    seg_count: int,
) -> list[dict[str, Any]]:
    """Recursively split requests into URL patterns.

    At each segment position (left-to-right), if there are few distinct values
    (<=_SPLIT_THRESHOLD), split into subgroups and recurse. Otherwise, treat
    the position as a wildcard.
    """
    all_segments = [_parse_request(r)[2] for r in requests]

    # Find the first segment position that should cause a split
    split_pos = None
    for i in range(seg_count):
        unique_values = {segs[i] for segs in all_segments}
        if 2 <= len(unique_values) <= _SPLIT_THRESHOLD:
            split_pos = i
            break

    if split_pos is not None:
        # Split into subgroups by the value at this position
        subgroups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for req in requests:
            _, _, segs = _parse_request(req)
            subgroups[segs[split_pos]].append(req)

        patterns: list[dict[str, Any]] = []
        for _, sub_reqs in subgroups.items():
            patterns.extend(_split_and_build_patterns(method, sub_reqs, seg_count))
        return patterns

    # No split needed — build a single pattern from this group
    pattern_segments: list[str] = []
    wildcard_count = 0
    for i in range(seg_count):
        unique_values = {segs[i] for segs in all_segments}
        if len(unique_values) == 1:
            pattern_segments.append(list(unique_values)[0])
        else:
            pattern_segments.append("[^/]+")
            wildcard_count += 1

    url_pattern = "/" + "/".join(pattern_segments)
    is_regex = wildcard_count > 0
    rep = _pick_representative(requests)

    return [
        {
            "method": method,
            "url_pattern": url_pattern,
            "is_regex": is_regex,
            "wildcard_count": wildcard_count,
            "response": _build_response_dict(rep),
        }
    ]


def _pick_representative(requests: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the best representative request: prefer first 2xx response."""
    for req in requests:
        if 200 <= req["response_status"] < 300:
            return req
    return requests[0]


def _build_response_dict(req: dict[str, Any]) -> dict[str, Any]:
    """Build a response dict from a request entry."""
    status = req["response_status"]
    body = req.get("response_body")

    if body is not None and 200 <= status < 300:
        return {"status_code": status, "json": _truncate_arrays(body)}
    elif status != 200:
        return {"status_code": status}
    else:
        return {"status_code": status}


# -- Code generation ---------------------------------------------------------


def _to_python_repr(value: Any, indent: int = 8) -> str:
    """Format a JSON-compatible value as valid Python source code.

    Uses repr() for proper Python literals (True/False/None instead of
    true/false/null), with indented formatting for readability.
    """
    return _format_python_value(value, indent, indent)


def _format_python_value(value: Any, current_indent: int, base_indent: int) -> str:
    """Recursively format a value as Python source."""
    if value is None:
        return "None"
    elif isinstance(value, bool):
        return "True" if value else "False"
    elif isinstance(value, (int, float)):
        return repr(value)
    elif isinstance(value, str):
        return repr(value)
    elif isinstance(value, list):
        if not value:
            return "[]"
        if len(value) == 1 and not isinstance(value[0], (dict, list)):
            return f"[{_format_python_value(value[0], current_indent, base_indent)}]"
        inner_indent = current_indent + 2
        prefix = " " * inner_indent
        items = []
        for item in value:
            items.append(
                f"{prefix}{_format_python_value(item, inner_indent, base_indent)}"
            )
        closing = " " * current_indent
        return "[\n" + ",\n".join(items) + f",\n{closing}]"
    elif isinstance(value, dict):
        if not value:
            return "{}"
        inner_indent = current_indent + 2
        prefix = " " * inner_indent
        items = []
        for k, v in value.items():
            key_str = repr(k)
            val_str = _format_python_value(v, inner_indent, base_indent)
            items.append(f"{prefix}{key_str}: {val_str}")
        closing = " " * current_indent
        return "{\n" + ",\n".join(items) + f",\n{closing}}}"
    else:
        return repr(value)


def _generate_routes_code(patterns: list[dict[str, Any]]) -> str:
    """Generate the add_route calls for InterceptTransport."""
    lines: list[str] = []
    for p in patterns:
        method = p["method"]
        url_pat = p["url_pattern"]
        resp = p["response"]

        resp_str = _to_python_repr(resp, indent=12)

        if p["is_regex"]:
            lines.append(
                f'        transport.add_route("{method}", r"{url_pat}", {resp_str})'
            )
        else:
            lines.append(
                f'        transport.add_route("{method}", "{url_pat}", {resp_str})'
            )

    return "\n".join(lines)


def _generate_test_file(
    patterns: list[dict[str, Any]],
    mapping_config: dict[str, Any],
    integration_config: dict[str, Any],
) -> str:
    """Generate the full test file content."""
    # Sanitize integration config
    sanitized_config = {
        "integration": {
            "identifier": integration_config.get("integration", {}).get(
                "identifier", "test-integration"
            ),
            "type": integration_config.get("integration", {}).get("type", "test"),
            "config": _sanitize_config(
                integration_config.get("integration", {}).get("config", {})
            ),
        }
    }

    routes_code = _generate_routes_code(patterns)
    mapping_str = _to_python_repr(mapping_config, indent=12)
    config_str = _to_python_repr(sanitized_config, indent=12)

    return textwrap.dedent(
        '''\
        """Auto-generated integration test from discovery.json.
        Edit the routes and assertions to match your testing needs.
        """
        import os
        from typing import Any

        import pytest
        from port_ocean.tests.integration import BaseIntegrationTest, InterceptTransport, ResyncResult


        class TestResync(BaseIntegrationTest):
            integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

            def create_third_party_transport(self) -> InterceptTransport:
                transport = InterceptTransport(strict=False)
                # --- auto-generated routes from discovery ---
        {routes}
                return transport

            def create_mapping_config(self) -> dict[str, Any]:
                return {mapping}

            def create_integration_config(self) -> dict[str, Any]:
                return {config}

            @pytest.mark.asyncio
            async def test_resync_creates_entities(self, resync: ResyncResult) -> None:
                """Smoke test: resync should produce entities without errors."""
                assert len(resync.errors) == 0, f"Resync had errors: {{resync.errors}}"
                assert len(resync.upserted_entities) > 0, "Expected entities to be upserted"

                # TODO: Add specific assertions for your entities
                # Example:
                # repos = [e for e in resync.upserted_entities if e.get("blueprint") == "myBlueprint"]
                # assert len(repos) == 2
        '''
    ).format(
        routes=routes_code,
        mapping=mapping_str,
        config=config_str,
    )


# -- Main entry point --------------------------------------------------------


def main() -> None:
    integration_path = Path.cwd()

    discovery_path = integration_path / ".port" / "resources" / "discovery.json"
    if not discovery_path.exists():
        print(
            "Error: No .port/resources/discovery.json found.\n"
            "Run `make test/discover` first to generate the discovery file.",
            file=sys.stderr,
        )
        sys.exit(1)

    discovery = json.loads(discovery_path.read_text())

    # Extract data from discovery
    third_party_requests = discovery.get("third_party_requests", [])
    mapping_config = discovery.get("mapping_config", {})
    integration_config = discovery.get("integration_config", {})

    if not third_party_requests:
        print(
            "Warning: No third-party requests found in discovery.json.\n"
            "The generated test will have no mock routes.",
            file=sys.stderr,
        )

    # Compute URL patterns
    patterns = _compute_url_patterns(third_party_requests)

    # Generate test file
    test_content = _generate_test_file(patterns, mapping_config, integration_config)

    # Write output
    tests_dir = integration_path / "tests"
    tests_dir.mkdir(exist_ok=True)

    output_path = tests_dir / "test_integration_resync.py"
    output_path.write_text(test_content)

    print(
        f"Generated {len(patterns)} route(s) from {len(third_party_requests)} request(s)"
    )
    print(f"Test file written to {output_path}")


if __name__ == "__main__":
    main()
