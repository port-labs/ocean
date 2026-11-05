import pytest
from pydantic.v1 import ValidationError

from aws_integration.overrides import (
    AWSCustomKindResourceConfig,
    AWSPortAppConfig,
    AWSS3BucketResourceConfig,
    AWSS3BucketSelector,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)


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
    resource = AWSCustomKindResourceConfig.parse_obj(
        {
            "kind": "AWS::IAM::Role",
            "selector": {
                "query": "true",
                "useGetResourceAPI": True,
                "resourceScope": "global",
            },
            "port": _minimal_port_mapping().dict(),
        }
    )
    assert resource.kind == "AWS::IAM::Role"
    assert resource.selector.use_get_resource_api is True
    assert resource.selector.resource_scope == "global"


def test_aws_custom_kind_rejects_invalid_type_string() -> None:
    with pytest.raises(ValidationError):
        AWSCustomKindResourceConfig.parse_obj(
            {
                "kind": "not-a-cloud-control-type",
                "selector": {"query": "true"},
                "port": _minimal_port_mapping().dict(),
            }
        )


def test_aws_port_app_config_allow_custom_kinds_is_disabled() -> None:
    assert AWSPortAppConfig.allow_custom_kinds is False


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


def test_aws_s3_bucket_parses_regional_bucket_discovery() -> None:
    config = AWSPortAppConfig.parse_obj(
        {
            "resources": [
                {
                    "kind": "AWS::S3::Bucket",
                    "selector": {"query": "true", "regionalBucketDiscovery": True},
                    "port": _minimal_port_mapping().dict(),
                }
            ]
        }
    )
    selector = config.resources[0].selector
    assert isinstance(selector, AWSS3BucketSelector)
    assert selector.regional_bucket_discovery is True
