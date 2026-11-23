from integration import FeatureFlagResourceConfig, LaunchDarklyPortAppConfig


def _flag_resource(selector: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "flag",
        "selector": selector,
        "port": {
            "entity": {
                "mappings": {
                    "identifier": ".key",
                    "title": ".name",
                    "blueprint": '"launchDarklyFeatureFlag"',
                }
            }
        },
    }


def test_flag_selector_include_environment_config_defaults_to_false() -> None:
    config = FeatureFlagResourceConfig.parse_obj(_flag_resource({"query": "true"}))

    assert config.selector.include_environment_config is False


def test_flag_selector_include_environment_config_alias() -> None:
    config = FeatureFlagResourceConfig.parse_obj(
        _flag_resource({"query": "true", "includeEnvironmentConfig": True})
    )

    assert config.selector.include_environment_config is True


def test_port_app_config_resolves_flag_resources_to_the_flag_config() -> None:
    app_config = LaunchDarklyPortAppConfig.parse_obj(
        {"resources": [_flag_resource({"query": "true"})]}
    )

    assert len(app_config.resources) == 1
    flag_resource = app_config.resources[0]
    assert isinstance(flag_resource, FeatureFlagResourceConfig)
    assert flag_resource.selector.include_environment_config is False
