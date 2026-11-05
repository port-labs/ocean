from aws.core.exporters.cloudcontrol.resource.scope import (
    is_cloud_control_global_kind,
    resolve_cloud_control_resource_scope,
)


def test_is_cloud_control_global_kind_for_known_global_services() -> None:
    assert is_cloud_control_global_kind("AWS::IAM::Role") is True
    assert is_cloud_control_global_kind("AWS::S3::Bucket") is True
    assert is_cloud_control_global_kind("AWS::CloudFront::Distribution") is True
    assert is_cloud_control_global_kind("AWS::Organizations::Account") is True


def test_is_cloud_control_global_kind_for_regional_and_invalid() -> None:
    assert is_cloud_control_global_kind("AWS::EC2::Instance") is False
    assert is_cloud_control_global_kind("AWS::Lambda::Function") is False
    assert is_cloud_control_global_kind("AWS::WAFv2::WebACL") is False
    assert is_cloud_control_global_kind("not-a-type") is False
    assert is_cloud_control_global_kind("") is False


def test_resolve_cloud_control_resource_scope_explicit_and_auto() -> None:
    assert (
        resolve_cloud_control_resource_scope("AWS::EC2::Instance", "global") == "global"
    )
    assert resolve_cloud_control_resource_scope("AWS::IAM::Role", "regional") == (
        "regional"
    )
    assert resolve_cloud_control_resource_scope("AWS::IAM::Role", "auto") == "global"
    assert (
        resolve_cloud_control_resource_scope("AWS::Lambda::Function", "auto")
        == "regional"
    )
