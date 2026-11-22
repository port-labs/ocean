from tools.integration_validation.runner.naming import (
    MAX_INTEGRATION_IDENTIFIER_LENGTH,
    build_integration_identifier,
    suffix_identifier,
)


def test_suffix_identifier_appends_sanitized_scenario_name() -> None:
    assert suffix_identifier("datadogTeam", "Team_Members enabled") == (
        "datadogTeam-team-members-enabled"
    )


def test_build_integration_identifier_sanitizes_scenario_name() -> None:
    assert build_integration_identifier("datadog", "happy_path") == (
        "validate-datadog-happy-path"
    )


def test_build_integration_identifier_truncates_to_port_limit() -> None:
    identifier = build_integration_identifier(
        "datadog", "team_members_enabled_with_pagination_and_rate_limits"
    )

    assert identifier == "validate-datadog-team-members-enabled-with-pagination"
    assert len(identifier) <= MAX_INTEGRATION_IDENTIFIER_LENGTH
