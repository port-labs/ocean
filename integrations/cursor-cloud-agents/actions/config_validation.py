from __future__ import annotations

from actions.exceptions import InvalidActionParametersException

API_VERSION_V0 = "v0"
API_VERSION_V1 = "v1"
SUPPORTED_API_VERSIONS = frozenset({API_VERSION_V0, API_VERSION_V1})


def parse_api_version(raw: object) -> str:
    if raw is None:
        return API_VERSION_V1
    if not isinstance(raw, str):
        raise InvalidActionParametersException("apiVersion must be a string")
    normalized = raw.strip().lower()
    if normalized not in SUPPORTED_API_VERSIONS:
        raise InvalidActionParametersException(
            f"apiVersion must be {API_VERSION_V0!r} or {API_VERSION_V1!r}"
        )
    return normalized


def validate_report_completion_policy(
    api_version: str,
    report_completion: bool,
) -> None:
    if api_version == API_VERSION_V1 and report_completion:
        raise InvalidActionParametersException(
            "reportCompletion is only supported on create_agent with apiVersion v0 "
            "(v1 has no webhooks)"
        )
