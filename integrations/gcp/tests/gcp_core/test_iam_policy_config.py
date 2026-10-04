import pytest
from pydantic.v1 import ValidationError

from gcp_core.overrides import (
    IAM_POLICY_KIND,
    GCPPortAppConfig,
    GCPResourceConfig,
    GCPIAMPolicyResourceConfig,
)
from port_ocean.core.handlers.port_app_config.validators import (
    validate_and_get_config_schema,
)


def _resource(kind: str, selector: dict[str, object]) -> dict[str, object]:
    return {
        "kind": kind,
        "selector": selector,
        "port": {
            "entity": {
                "mappings": {
                    "identifier": ".name",
                    "blueprint": '"gcpCloudResource"',
                }
            }
        },
    }


def test_iam_policy_kind_parses_asset_types_and_policy_query() -> None:
    config = GCPPortAppConfig.parse_obj(
        {
            "resources": [
                _resource(
                    IAM_POLICY_KIND,
                    {
                        "query": "true",
                        "assetTypes": ["  iam.googleapis.com/ServiceAccount  "],
                        "policyQuery": "  memberTypes:serviceAccount  ",
                    },
                )
            ]
        }
    )

    resource = config.resources[0]
    assert isinstance(resource, GCPIAMPolicyResourceConfig)
    assert resource.selector.asset_types == ["iam.googleapis.com/ServiceAccount"]
    assert resource.selector.policy_query == "memberTypes:serviceAccount"


def test_blank_policy_query_is_unset() -> None:
    config = GCPPortAppConfig.parse_obj(
        {
            "resources": [
                _resource(
                    IAM_POLICY_KIND,
                    {
                        "query": "true",
                        "assetTypes": ["cloudresourcemanager.googleapis.com/Project"],
                        "policyQuery": "   ",
                    },
                )
            ]
        }
    )

    resource = config.resources[0]
    assert isinstance(resource, GCPIAMPolicyResourceConfig)
    assert resource.selector.policy_query is None


def test_iam_policy_kind_requires_asset_types() -> None:
    with pytest.raises(ValidationError, match="assetTypes"):
        GCPPortAppConfig.parse_obj(
            {
                "resources": [
                    _resource(
                        IAM_POLICY_KIND,
                        {"query": "true"},
                    )
                ]
            }
        )


def test_existing_resource_kinds_stay_unchanged() -> None:
    config = GCPPortAppConfig.parse_obj(
        {
            "resources": [
                _resource(
                    "cloudresourcemanager.googleapis.com/Project",
                    {"query": "true"},
                ),
                _resource(
                    "compute.googleapis.com/Instance",
                    {"query": "true"},
                ),
            ]
        }
    )

    assert config.resources[0].kind == "cloudresourcemanager.googleapis.com/Project"
    assert isinstance(config.resources[1], GCPResourceConfig)
    assert config.resources[1].kind == "compute.googleapis.com/Instance"


def test_iam_policy_kind_is_in_the_config_schema() -> None:
    schema = validate_and_get_config_schema(GCPPortAppConfig)
    kind_schema = schema["kinds"][IAM_POLICY_KIND]
    properties = kind_schema["selectors"]["properties"]

    assert "assetTypes" in properties
    assert "policyQuery" in properties
    assert "assetTypes" in kind_schema["selectors"].get("required", [])
