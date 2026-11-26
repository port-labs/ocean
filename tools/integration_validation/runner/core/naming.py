from __future__ import annotations

# Port rejects longer integration installation ids.
MAX_INTEGRATION_IDENTIFIER_LENGTH = 53


def suffix_identifier(identifier: str, scenario_name: str) -> str:
    return f"{identifier}-{scenario_name.replace('_', '-')}"


def build_integration_identifier(integration_name: str, scenario_name: str) -> str:
    identifier = (
        f"validate-{integration_name}-{scenario_name.replace('_', '-')}".lower()
    )
    return identifier[:MAX_INTEGRATION_IDENTIFIER_LENGTH].rstrip("-")
