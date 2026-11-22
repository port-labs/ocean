from __future__ import annotations

import re

# Port rejects longer integration installation ids.
MAX_INTEGRATION_IDENTIFIER_LENGTH = 53
_UNSAFE_IDENTIFIER_CHARS = re.compile(r"[^a-z0-9]+")


def suffix_identifier(identifier: str, scenario_name: str) -> str:
    return f"{identifier}-{_sanitize(scenario_name)}"


def build_integration_identifier(integration_name: str, scenario_name: str) -> str:
    identifier = _sanitize(f"validate-{integration_name}-{scenario_name}")
    return identifier[:MAX_INTEGRATION_IDENTIFIER_LENGTH].rstrip("-")


def _sanitize(value: str) -> str:
    return _UNSAFE_IDENTIFIER_CHARS.sub("-", value.lower()).strip("-")
