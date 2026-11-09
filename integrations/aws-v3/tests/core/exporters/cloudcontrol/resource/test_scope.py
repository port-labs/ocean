from aws.core.exporters.cloudcontrol.resource.scope import (
    is_cloud_control_global_kind,
    resolve_cloud_control_is_regional,
)
from aws_integration.cloud_control_scope import CloudControlResourceScope


def test_is_cloud_control_global_kind_for_known_global_services() -> None:
    assert is_cloud_control_global_kind("AWS::IAM::Role") is True
    assert is_cloud_control_global_kind("AWS::S3::Bucket") is True
    assert is_cloud_control_global_kind("AWS::CloudFront::Distribution") is True
    assert is_cloud_control_global_kind("AWS::Organizations::Account") is True


def test_is_cloud_control_global_kind_for_regional_services() -> None:
    assert is_cloud_control_global_kind("AWS::EC2::Instance") is False
    assert is_cloud_control_global_kind("AWS::Lambda::Function") is False
    assert is_cloud_control_global_kind("AWS::WAFv2::WebACL") is False


def test_resolve_cloud_control_is_regional_explicit_and_auto() -> None:
    assert (
        resolve_cloud_control_is_regional(
            "AWS::EC2::Instance", CloudControlResourceScope.GLOBAL
        )
        is False
    )
    assert (
        resolve_cloud_control_is_regional(
            "AWS::IAM::Role", CloudControlResourceScope.REGIONAL
        )
        is True
    )
    assert (
        resolve_cloud_control_is_regional(
            "AWS::IAM::Role", CloudControlResourceScope.AUTO
        )
        is False
    )
    assert (
        resolve_cloud_control_is_regional(
            "AWS::Lambda::Function", CloudControlResourceScope.AUTO
        )
        is True
    )
