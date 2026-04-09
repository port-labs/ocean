from integration import AikidoPortAppConfig


def test_aikido_app_config_schema_includes_new_resource_kinds():
    """
    Ensure that the generated config schema for AikidoPortAppConfig
    includes the newly added resource kinds, to prevent regressions in
    schema extraction / UI compliance.
    """

    schema = AikidoPortAppConfig.schema()

    def _collect_enum_values(obj, enums: set[str]) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "enum" and isinstance(value, list):
                    enums.update(str(item) for item in value)
                else:
                    _collect_enum_values(value, enums)
        elif isinstance(obj, list):
            for item in obj:
                _collect_enum_values(item, enums)

    enum_values: set[str] = set()
    _collect_enum_values(schema, enum_values)

    assert "issues" in enum_values
    assert "issue_groups" in enum_values
    assert "team" in enum_values
