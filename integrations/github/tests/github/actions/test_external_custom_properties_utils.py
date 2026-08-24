import pytest

from github.actions.external_custom_properties.utils import (
    group_repository_values_by_org,
)
from github.helpers.exceptions import InvalidActionParametersException


class TestGroupRepositoryValuesByOrg:
    def test_groups_by_explicit_org(self) -> None:
        grouped = group_repository_values_by_org(
            [
                {
                    "org": "port-labs",
                    "repository_name": "ocean",
                    "value": "Deprecated",
                },
                {
                    "org": "other-org",
                    "repository_name": "api",
                    "value": "production",
                },
            ],
            default_org=None,
        )

        assert grouped == {
            "port-labs": [{"repository_name": "ocean", "value": "Deprecated"}],
            "other-org": [{"repository_name": "api", "value": "production"}],
        }

    def test_uses_default_org(self) -> None:
        grouped = group_repository_values_by_org(
            [{"repository_name": "ocean", "value": None}],
            default_org="port-labs",
        )

        assert grouped == {
            "port-labs": [{"repository_name": "ocean", "value": None}],
        }

    def test_missing_repository_name_fails(self) -> None:
        with pytest.raises(
            InvalidActionParametersException,
            match="repositoryValues\\[0\\]\\.repository_name is required",
        ):
            group_repository_values_by_org(
                [{"org": "port-labs", "value": "x"}],
                default_org=None,
            )
