import json
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic.v1 import ValidationError

from gcp_core.overrides import (
    GCPPortAppConfig,
    GCPProjectResourceConfig,
    GCPResourceConfig,
)
from gcp_core.search.cloud_asset_registry import get_api, registered_config_classes
from gcp_core.search.iam_policies import IAM_POLICY_KIND, IamPolicyResourceConfig
from port_ocean.core.handlers.port_app_config.models import CUSTOM_KIND
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


def test_resource_kinds_stay_on_the_original_selector() -> None:
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

    project = config.resources[0]
    instance = config.resources[1]
    assert isinstance(project, GCPProjectResourceConfig)
    assert isinstance(instance, GCPResourceConfig)
    assert not hasattr(project.selector, "content_type")
    assert not hasattr(instance.selector, "asset_query")
    assert get_api("compute.googleapis.com/Instance") is None


def test_iam_policy_kind_parses_asset_types_and_policy_query() -> None:
    config = GCPPortAppConfig.parse_obj(
        {
            "resources": [
                _resource(
                    IAM_POLICY_KIND,
                    {
                        "query": "true",
                        "assetTypes": [
                            "  cloudresourcemanager.googleapis.com/Project  "
                        ],
                        "policyQuery": "  memberTypes:serviceAccount  ",
                    },
                )
            ]
        }
    )

    resource = config.resources[0]
    assert isinstance(resource, IamPolicyResourceConfig)
    assert resource.selector.asset_types == [
        "cloudresourcemanager.googleapis.com/Project"
    ]
    assert resource.selector.policy_query == "memberTypes:serviceAccount"
    api = get_api(IAM_POLICY_KIND)
    assert api is not None
    assert api.config_cls is IamPolicyResourceConfig


def test_blank_policy_query_is_unset() -> None:
    config = GCPPortAppConfig.parse_obj(
        {
            "resources": [
                _resource(
                    IAM_POLICY_KIND,
                    {
                        "query": "true",
                        "assetTypes": ["iam.googleapis.com/ServiceAccount"],
                        "policyQuery": "   ",
                    },
                )
            ]
        }
    )

    resource = config.resources[0]
    assert isinstance(resource, IamPolicyResourceConfig)
    assert resource.selector.policy_query is None


def test_iam_policy_kind_requires_asset_types() -> None:
    with pytest.raises(ValidationError, match="assetTypes"):
        GCPPortAppConfig.parse_obj(
            {
                "resources": [
                    _resource(IAM_POLICY_KIND, {"query": "true"}),
                ]
            }
        )


def test_iam_policy_schema_documents_search_all_iam_policies_query() -> None:
    schema = validate_and_get_config_schema(GCPPortAppConfig)
    kind_schema = schema["kinds"][IAM_POLICY_KIND]
    properties = kind_schema["selectors"]["properties"]
    custom_properties = schema["kinds"][CUSTOM_KIND]["selectors"]["properties"]

    assert "assetTypes" in properties
    assert "searchAllIamPolicies" in properties["policyQuery"]["description"]
    assert "not sent to searchAllResources" in properties["policyQuery"]["description"]
    assert "contentType" not in custom_properties
    assert "assetQuery" not in custom_properties
    assert "policyQuery" not in custom_properties
    assert registered_config_classes() == (IamPolicyResourceConfig,)


def test_iam_policy_example_mapping_parses() -> None:
    example = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "iam-policy-binding"
        / "mapping.yaml"
    )
    loaded = yaml.safe_load(example.read_text())
    config = GCPPortAppConfig.parse_obj(loaded)
    raw = json.loads((example.parent / "raw.json").read_text())
    resource = config.resources[0]

    assert isinstance(resource, IamPolicyResourceConfig)
    assert resource.selector.policy_query == "memberTypes:serviceAccount"
    assert raw["role"] == "roles/container.developer"
    assert raw["member"].startswith("serviceAccount:")
