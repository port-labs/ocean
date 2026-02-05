import pytest

from github.helpers.port_app_config import ORG_CONFIG_FILE, validate_config_file_name


class TestValidateConfigFileName:
    def test_defaults_to_port_app_config_yml_when_not_provided(self) -> None:
        assert validate_config_file_name(None) == f"{ORG_CONFIG_FILE}.yml"

    @pytest.mark.parametrize(
        "name",
        [
            f"{ORG_CONFIG_FILE}.yml",
            f"{ORG_CONFIG_FILE}.yaml",
            f"{ORG_CONFIG_FILE}-custom.yaml",
        ],
    )
    def test_accepts_valid_yaml_names(self, name: str) -> None:
        assert validate_config_file_name(name) == name

    @pytest.mark.parametrize(
        "name",
        [
            "not-port-app-config.yml",
            "foo.yaml",
            "port.yml",
        ],
    )
    def test_rejects_names_that_do_not_start_with_expected_prefix(
        self, name: str
    ) -> None:
        with pytest.raises(ValueError, match="must start with"):
            validate_config_file_name(name)

    @pytest.mark.parametrize(
        "name",
        [
            f"{ORG_CONFIG_FILE}.json",
            f"{ORG_CONFIG_FILE}.txt",
            ORG_CONFIG_FILE,  # no suffix
        ],
    )
    def test_rejects_names_that_are_not_yaml(self, name: str) -> None:
        with pytest.raises(ValueError, match="must end with"):
            validate_config_file_name(name)
