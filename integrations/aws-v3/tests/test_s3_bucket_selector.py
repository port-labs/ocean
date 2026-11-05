from typing import Any

import pytest

from aws_integration.overrides import (
    AWSPortAppConfig,
    AWSS3BucketResourceConfig,
    AWSS3BucketSelector,
    RegionPolicy,
)


def _resource(kind: str, selector: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "selector": selector,
        "port": {
            "entity": {
                "mappings": {
                    "identifier": ".Properties.Arn",
                    "blueprint": '"bp"',
                }
            }
        },
    }


class TestAWSS3BucketSelector:
    def test_flag_defaults_to_false(self) -> None:
        selector = AWSS3BucketSelector(query="true")
        assert selector.regional_bucket_discovery is False

    @pytest.mark.parametrize(
        "region_policy",
        [
            RegionPolicy(),
            RegionPolicy(allow=["us-east-1"]),
            RegionPolicy(deny=["us-west-2"]),
        ],
    )
    def test_flag_parses_with_or_without_region_policy(
        self, region_policy: RegionPolicy
    ) -> None:
        selector = AWSS3BucketSelector(
            query="true",
            regionPolicy=region_policy,
            regionalBucketDiscovery=True,
        )
        assert selector.regional_bucket_discovery is True

    def test_s3_resource_config_uses_s3_selector(self) -> None:
        config = AWSPortAppConfig.parse_obj(
            {
                "resources": [
                    _resource(
                        "AWS::S3::Bucket",
                        {"query": "true", "regionalBucketDiscovery": True},
                    ),
                    _resource("AWS::EC2::Instance", {"query": "true"}),
                ]
            }
        )
        s3, ec2 = config.resources
        assert isinstance(s3, AWSS3BucketResourceConfig)
        assert isinstance(s3.selector, AWSS3BucketSelector)
        assert s3.selector.regional_bucket_discovery is True
        assert not isinstance(ec2.selector, AWSS3BucketSelector)
