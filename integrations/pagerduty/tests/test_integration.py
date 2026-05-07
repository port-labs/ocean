from port_ocean.core.handlers.port_app_config.validators import (
    validate_and_get_config_schema,
)

from integration import PagerdutyPortAppConfig


def test_pagerduty_port_app_config_schema_generation_includes_all_resource_kinds() -> (
    None
):
    """Validates that schema generation succeeds and all supported resource kinds are present.

    Also exercises the allow_custom_kinds=True path to prevent regressions in
    kind/selector propagation.
    """
    schema = validate_and_get_config_schema(PagerdutyPortAppConfig)

    assert schema, "Expected a non-empty schema for PagerdutyPortAppConfig"
    assert (
        PagerdutyPortAppConfig.allow_custom_kinds
    ), "allow_custom_kinds must be True to support custom PagerDuty resource kinds"

    kinds = schema.get("kinds", {})
    expected_kinds = {
        "incidents",
        "services",
        "schedules",
        "oncalls",
        "escalation_policies",
    }

    missing_kinds = {kind for kind in expected_kinds if kind not in kinds}
    assert not missing_kinds, f"Missing resource kinds in schema: {missing_kinds}"
