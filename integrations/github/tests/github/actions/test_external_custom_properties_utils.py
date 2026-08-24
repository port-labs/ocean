import pytest
from pydantic.v1 import ValidationError

from github.actions.external_custom_properties.utils import RepositoryValuesInput
from github.helpers.exceptions import InvalidActionParametersException


class TestRepositoryValuesInput:
    def test_groups_by_explicit_org(self) -> None:
        grouped = RepositoryValuesInput(
            repository_values=[
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
            ]
        ).group_by_org()

        assert {
            organization: [value.dict() for value in values]
            for organization, values in grouped.items()
        } == {
            "port-labs": [{"repository_name": "ocean", "value": "Deprecated"}],
            "other-org": [{"repository_name": "api", "value": "production"}],
        }

    def test_uses_default_org(self) -> None:
        grouped = RepositoryValuesInput(
            org="port-labs",
            repository_values=[{"repository_name": "ocean", "value": None}],
        ).group_by_org()

        assert {
            organization: [value.dict() for value in values]
            for organization, values in grouped.items()
        } == {
            "port-labs": [{"repository_name": "ocean", "value": None}],
        }

    def test_missing_org_fails(self) -> None:
        with pytest.raises(
            InvalidActionParametersException,
            match="No org provided for repository ocean",
        ):
            RepositoryValuesInput(
                repository_values=[{"repository_name": "ocean", "value": "x"}]
            ).group_by_org()

    def test_preserves_falsy_non_empty_values(self) -> None:
        grouped = RepositoryValuesInput(
            org="port-labs",
            repository_values=[{"repository_name": "ocean", "value": 0}],
        ).group_by_org()

        assert {
            organization: [value.dict() for value in values]
            for organization, values in grouped.items()
        } == {
            "port-labs": [{"repository_name": "ocean", "value": "0"}],
        }

    def test_empty_string_value_becomes_none(self) -> None:
        grouped = RepositoryValuesInput(
            org="port-labs",
            repository_values=[{"repository_name": "ocean", "value": ""}],
        ).group_by_org()

        assert {
            organization: [value.dict() for value in values]
            for organization, values in grouped.items()
        } == {
            "port-labs": [{"repository_name": "ocean", "value": None}],
        }

    def test_empty_repository_values_fails(self) -> None:
        with pytest.raises(ValidationError):
            RepositoryValuesInput(repository_values=[])
