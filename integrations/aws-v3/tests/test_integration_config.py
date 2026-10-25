from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic.v1 import ValidationError

from integration import (
    AWSCustomKindResourceConfig,
    AWSPortAppConfig,
    AWSS3BucketResourceConfig,
    AWSAPIPortAppConfig,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.models import IntegrationFeatureFlag


def _minimal_port_mapping() -> PortResourceConfig:
    return PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier='."identifier"',
                title='."title"',
                blueprint='"testBlueprint"',
            )
        )
    )


def test_aws_custom_kind_resource_config_parses_cloud_control_type() -> None:
    config = AWSPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "AWS::IAM::Role",
                    "selector": {
                        "query": "true",
                        "useGetResourceAPI": True,
                        "resourceScope": "global",
                    },
                    "port": _minimal_port_mapping().dict(),
                }
            ]
        }
    )
    assert len(config.resources) == 1
    resource = config.resources[0]
    assert isinstance(resource, AWSCustomKindResourceConfig)
    assert resource.kind == "AWS::IAM::Role"
    assert resource.selector.use_get_resource_api is True
    assert resource.selector.resource_scope == "global"


def test_aws_s3_bucket_still_resolves_to_first_class_config() -> None:
    config = AWSPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "AWS::S3::Bucket",
                    "selector": {"query": "true"},
                    "port": _minimal_port_mapping().dict(),
                }
            ]
        }
    )
    assert len(config.resources) == 1
    assert isinstance(config.resources[0], AWSS3BucketResourceConfig)
    assert config.resources[0].kind == "AWS::S3::Bucket"


def test_aws_custom_kind_rejects_invalid_type_string() -> None:
    with pytest.raises(ValidationError):
        AWSPortAppConfig.parse_obj(
            {
                "resources": [
                    {
                        "kind": "not-a-cloud-control-type",
                        "selector": {"query": "true"},
                        "port": _minimal_port_mapping().dict(),
                    }
                ]
            }
        )


def test_aws_port_app_config_allow_custom_kinds_is_enabled() -> None:
    assert AWSPortAppConfig.allow_custom_kinds is True


@pytest.mark.asyncio
async def test_get_port_app_config_rejects_custom_kinds_when_feature_flag_off(
    mock_ocean_context: None,
) -> None:
    from port_ocean.context.ocean import ocean

    ocean.port_client.get_organization_feature_flags = AsyncMock(return_value=[])

    context = MagicMock(spec=PortOceanContext)
    context.config.port.port_app_config_cache_ttl = 300
    handler = AWSAPIPortAppConfig(context)
    handler.CONFIG_CLASS = AWSPortAppConfig
    handler.mock_get_port_app_config = MagicMock(
        return_value={
            "resources": [
                {
                    "kind": "AWS::IAM::Role",
                    "selector": {"query": "true"},
                    "port": _minimal_port_mapping().dict(),
                }
            ]
        }
    )

    async def _get_port_app_config() -> dict:
        return handler.mock_get_port_app_config()

    handler._get_port_app_config = _get_port_app_config  # type: ignore[method-assign]

    async with event_context(EventType.RESYNC, trigger_type="machine"):
        with pytest.raises(ValidationError, match="AWS_V3_CUSTOM_KINDS_ENABLED"):
            await handler.get_port_app_config(use_cache=False)


@pytest.mark.asyncio
async def test_get_port_app_config_allows_custom_kinds_when_feature_flag_on(
    mock_ocean_context: None,
) -> None:
    from port_ocean.context.ocean import ocean

    ocean.port_client.get_organization_feature_flags = AsyncMock(
        return_value=[IntegrationFeatureFlag.AWS_V3_CUSTOM_KINDS_ENABLED]
    )

    context = MagicMock(spec=PortOceanContext)
    context.config.port.port_app_config_cache_ttl = 300
    handler = AWSAPIPortAppConfig(context)
    handler.CONFIG_CLASS = AWSPortAppConfig
    handler.mock_get_port_app_config = MagicMock(
        return_value={
            "resources": [
                {
                    "kind": "AWS::IAM::Role",
                    "selector": {"query": "true"},
                    "port": _minimal_port_mapping().dict(),
                }
            ]
        }
    )

    async def _get_port_app_config() -> dict:
        return handler.mock_get_port_app_config()

    handler._get_port_app_config = _get_port_app_config  # type: ignore[method-assign]

    async with event_context(EventType.RESYNC, trigger_type="machine"):
        config = await handler.get_port_app_config(use_cache=False)
    assert isinstance(config.resources[0], AWSCustomKindResourceConfig)
