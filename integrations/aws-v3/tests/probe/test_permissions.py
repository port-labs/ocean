from aws_integration.overrides import AWSCustomKindResourceConfig, AWSPortAppConfig
from aws.probe.permissions import CUSTOM_KIND_UNVERIFIED_NOTE, AwsKindPermissionVerdict
from port_ocean.core.handlers.port_app_config.models import CUSTOM_KIND
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import PermissionCombination, ProbeCheckStatus


def _custom_kind_verdict() -> AwsKindPermissionVerdict:
    verdict = AwsKindPermissionVerdict()
    verdict._kind_permissions = {
        CUSTOM_KIND: AWSCustomKindResourceConfig.probe_permissions
    }
    return verdict


def test_aws_kind_permission_verdict_loads_kind_probe_permissions() -> None:
    # Arrange
    verdict = AwsKindPermissionVerdict()

    # Act + Assert
    assert verdict.kind_permissions == get_kind_probe_permissions(AWSPortAppConfig)
    assert verdict.combination is PermissionCombination.AND
    assert verdict.kind_permissions["AWS::EC2::Instance"] == ("ec2:DescribeInstances",)
    assert verdict.kind_permissions["AWS::S3::Bucket"] == (
        "s3:ListAllMyBuckets",
        "s3:GetBucketTagging",
    )


def test_verdict_succeeds_when_required_actions_are_allowed() -> None:
    # Arrange
    verdict = AwsKindPermissionVerdict()

    # Act
    status, message = verdict.verdict(
        "AWS::EC2::Instance",
        {"ec2:DescribeInstances": "allowed"},
    )

    # Assert
    assert status is ProbeCheckStatus.SUCCESS
    assert "ec2:DescribeInstances" in message


def test_verdict_fails_on_explicit_or_implicit_deny() -> None:
    # Arrange
    verdict = AwsKindPermissionVerdict()

    # Act
    explicit_status, _ = verdict.verdict(
        "AWS::EC2::Instance",
        {"ec2:DescribeInstances": "explicitDeny"},
    )
    implicit_status, _ = verdict.verdict(
        "AWS::EC2::Instance",
        {"ec2:DescribeInstances": "implicitDeny"},
    )

    # Assert
    assert explicit_status is ProbeCheckStatus.FAILURE
    assert implicit_status is ProbeCheckStatus.FAILURE


def test_verdict_is_unknown_when_simulation_omits_an_action() -> None:
    # Arrange
    verdict = AwsKindPermissionVerdict()

    # Act
    status, message = verdict.verdict("AWS::EC2::Instance", {})

    # Assert
    assert status is ProbeCheckStatus.UNKNOWN
    assert "ec2:DescribeInstances" in message


def test_custom_kind_verdict_succeeds_with_unverified_service_note() -> None:
    # Arrange
    verdict = _custom_kind_verdict()

    # Act
    status, message = verdict.verdict(
        CUSTOM_KIND,
        {
            "cloudformation:ListResources": "allowed",
            "cloudformation:GetResource": "allowed",
        },
    )

    # Assert
    assert status is ProbeCheckStatus.SUCCESS
    assert "cloudformation:ListResources" in message
    assert message.endswith(CUSTOM_KIND_UNVERIFIED_NOTE)


def test_custom_kind_verdict_fails_without_cloud_control_access() -> None:
    # Arrange
    verdict = _custom_kind_verdict()

    # Act
    status, message = verdict.verdict(
        CUSTOM_KIND,
        {
            "cloudformation:ListResources": "allowed",
            "cloudformation:GetResource": "implicitDeny",
        },
    )

    # Assert
    assert status is ProbeCheckStatus.FAILURE
    assert "cloudformation:GetResource" in message
    assert CUSTOM_KIND_UNVERIFIED_NOTE not in message
