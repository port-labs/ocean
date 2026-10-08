from integration import AWSPortAppConfig
from aws.probe.permissions import AwsKindPermissionVerdict
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import PermissionCombination, ProbeCheckStatus


def test_aws_kind_permission_verdict_loads_kind_probe_permissions() -> None:
    # Arrange
    verdict = AwsKindPermissionVerdict()

    # Act + Assert
    assert verdict.kind_permissions == get_kind_probe_permissions(AWSPortAppConfig)
    assert verdict.combination is PermissionCombination.AND
    assert verdict.kind_permissions["AWS::EC2::Instance"] == ("ec2:DescribeInstances",)
    assert verdict.kind_permissions["AWS::S3::Bucket"] == ("s3:ListAllMyBuckets",)


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
