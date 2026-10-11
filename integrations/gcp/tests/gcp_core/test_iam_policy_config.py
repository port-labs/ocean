import json
from collections.abc import Generator
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import port_ocean.context.ocean as ocean_module
import pytest
import yaml  # type: ignore[import-untyped]
from pydantic.v1 import ValidationError

from gcp_core.overrides import (
    GCPPortAppConfig,
    GCPProjectResourceConfig,
    GCPResourceConfig,
    GCPResourceSelector,
)
from port_ocean.context.ocean import PortOceanContext, initialize_port_ocean_context
from port_ocean.core.handlers.port_app_config.models import CUSTOM_KIND
from port_ocean.core.handlers.port_app_config.validators import (
    validate_and_get_config_schema,
)


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    mock_app = MagicMock()
    mock_app.config.integration.config = {"search_all_resources_per_minute_quota": 100}
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)
    yield
    ocean_module._port_ocean = PortOceanContext(None)


def _selector(config: GCPPortAppConfig, index: int = 0) -> GCPResourceSelector:
    return cast(GCPResourceSelector, config.resources[index].selector)


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


def test_default_content_type_is_resource_and_preserves_existing_kinds() -> None:
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
    assert project.selector.content_type == "RESOURCE"
    assert project.selector.asset_query is None
    assert isinstance(instance, GCPResourceConfig)
    assert instance.selector.content_type == "RESOURCE"
    assert instance.kind == "compute.googleapis.com/Instance"


def test_content_type_and_asset_query_parse_for_iam_policy() -> None:
    config = GCPPortAppConfig.parse_obj(
        {
            "resources": [
                _resource(
                    "cloudresourcemanager.googleapis.com/Project",
                    {
                        "query": "true",
                        "contentType": " iam_policy ",
                        "assetQuery": "  memberTypes:serviceAccount  ",
                    },
                )
            ]
        }
    )

    resource = config.resources[0]
    assert isinstance(resource, GCPProjectResourceConfig)
    assert resource.selector.content_type == "IAM_POLICY"
    assert resource.selector.asset_query == "memberTypes:serviceAccount"


@pytest.mark.parametrize(
    "content_type",
    ["ORG_POLICY", "ACCESS_POLICY", "OS_INVENTORY", "RELATIONSHIP"],
)
def test_asset_query_is_rejected_for_list_assets_content_types(
    content_type: str,
) -> None:
    with pytest.raises(ValidationError, match="assetQuery"):
        GCPPortAppConfig.parse_obj(
            {
                "resources": [
                    _resource(
                        "compute.googleapis.com/Instance",
                        {
                            "query": "true",
                            "contentType": content_type,
                            "assetQuery": "labels.env:prod",
                        },
                    )
                ]
            }
        )


def test_list_assets_content_type_without_query_is_valid() -> None:
    config = GCPPortAppConfig.parse_obj(
        {
            "resources": [
                _resource(
                    "compute.googleapis.com/Instance",
                    {"query": "true", "contentType": "OS_INVENTORY"},
                )
            ]
        }
    )

    assert _selector(config).content_type == "OS_INVENTORY"
    assert _selector(config).asset_query is None


def test_resource_asset_query_is_rejected_for_product_api_kinds() -> None:
    with pytest.raises(ValidationError, match="searchAllResources"):
        GCPPortAppConfig.parse_obj(
            {
                "resources": [
                    _resource(
                        "pubsub.googleapis.com/Topic",
                        {"query": "true", "assetQuery": "labels.env:prod"},
                    )
                ]
            }
        )


def test_non_resource_content_type_is_allowed_on_product_api_kinds() -> None:
    config = GCPPortAppConfig.parse_obj(
        {
            "resources": [
                _resource(
                    "pubsub.googleapis.com/Topic",
                    {
                        "query": "true",
                        "contentType": "IAM_POLICY",
                        "assetQuery": "memberTypes:serviceAccount",
                    },
                )
            ]
        }
    )

    assert _selector(config).content_type == "IAM_POLICY"
    assert _selector(config).asset_query == "memberTypes:serviceAccount"


def test_cloud_resource_rejects_content_type() -> None:
    with pytest.raises(ValidationError, match="cloudResource"):
        GCPPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "cloudResource",
                        "selector": {
                            "query": "true",
                            "resourceKinds": ["compute.googleapis.com/Instance"],
                            "contentType": "IAM_POLICY",
                        },
                        "port": {
                            "entity": {
                                "mappings": {
                                    "identifier": ".name",
                                    "blueprint": '"gcpCloudResource"',
                                }
                            }
                        },
                    }
                ]
            }
        )


def test_content_type_is_in_the_selector_schema() -> None:
    schema = validate_and_get_config_schema(GCPPortAppConfig)
    properties = schema["kinds"][CUSTOM_KIND]["selectors"]["properties"]

    assert properties["contentType"]["default"] == "RESOURCE"
    assert "Server-side asset query" in properties["assetQuery"]["title"]
    assert "contentType" not in schema["kinds"][CUSTOM_KIND]["selectors"].get(
        "required", []
    )


def test_list_assets_fallback_quota_is_the_documented_limit() -> None:
    from gcp_core.helpers.ratelimiter.overrides import ListAssetsQpmPerProject

    assert ListAssetsQpmPerProject._default_quota == 100


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

    assert _selector(config).content_type == "IAM_POLICY"
    assert _selector(config).asset_query == "memberTypes:serviceAccount"
    assert config.resources[0].port.items_to_parse == ".iam_policy.bindings"
    assert raw["iam_policy"]["bindings"][0]["role"] == "roles/container.developer"
