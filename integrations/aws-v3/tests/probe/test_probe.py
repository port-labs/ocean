from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from aiobotocore.session import AioSession

from aws.auth.utils import AWSSessionError
from aws.probe.probe import AwsPermissionProbe
from aws.probe.simulator import MISSING_SIMULATE_PERMISSIONS_MESSAGE, SimulateOutcome
from port_ocean.core.probe import ProbeCheckStatus, ProbeContext, ProbeStatus
from tests.probe.conftest import client_error, make_session


async def _accounts(
    *pairs: tuple[dict[str, str], AioSession],
) -> AsyncIterator[tuple[dict[str, str], AioSession]]:
    for pair in pairs:
        yield pair


@pytest.mark.asyncio
async def test_probe_fails_when_session_initialization_fails(
    probe_context: ProbeContext,
) -> None:
    # Arrange
    probe_context.available_kinds = ["AWS::EC2::Instance"]

    with (
        patch(
            "aws.probe.probe.initialize_aws_account_sessions",
            new_callable=AsyncMock,
            side_effect=AWSSessionError("boom"),
        ),
        patch(
            "aws.probe.probe.clear_aws_account_sessions",
            new_callable=AsyncMock,
        ) as clear_sessions,
    ):
        # Act
        await AwsPermissionProbe(probe_context).run()

    # Assert
    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message == "Failed to verify AWS authentication."
    assert probe_context.checks == []
    clear_sessions.assert_not_awaited()


@pytest.mark.asyncio
async def test_probe_creates_account_and_region_scopes_for_all_kinds(
    probe_context: ProbeContext,
) -> None:
    # Arrange
    probe_context.available_kinds = ["AWS::EC2::Instance", "AWS::S3::Bucket"]
    session_a = make_session(account_id="111122223333")
    session_b = make_session(account_id="444455556666")

    with (
        patch(
            "aws.probe.probe.initialize_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.clear_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.get_all_account_sessions",
            return_value=_accounts(
                ({"Id": "111122223333", "Name": "A"}, session_a),
                ({"Id": "444455556666", "Name": "B"}, session_b),
            ),
        ),
        patch(
            "aws.probe.probe.get_allowed_regions",
            new_callable=AsyncMock,
            side_effect=[["us-east-1", "eu-west-1"], ["us-east-1", "eu-west-1"]],
        ),
    ):
        # Act
        await AwsPermissionProbe(probe_context).run()

    # Assert
    assert len(probe_context.checks) == 8
    scopes = {
        (check.scopes["account"], check.scopes["region"])
        for check in probe_context.checks
    }
    assert scopes == {
        ("111122223333", "us-east-1"),
        ("111122223333", "eu-west-1"),
        ("444455556666", "us-east-1"),
        ("444455556666", "eu-west-1"),
    }
    assert all(
        "account" in check.scopes and "region" in check.scopes
        for check in probe_context.checks
    )
    assert all(
        check.status is ProbeCheckStatus.SUCCESS for check in probe_context.checks
    )


@pytest.mark.asyncio
async def test_probe_marks_explicit_deny_as_failure(
    probe_context: ProbeContext,
) -> None:
    # Arrange
    probe_context.available_kinds = ["AWS::EC2::Instance", "AWS::S3::Bucket"]
    session = make_session(
        simulate_response={
            "EvaluationResults": [
                {
                    "EvalActionName": "ec2:DescribeInstances",
                    "EvalDecision": "explicitDeny",
                },
                {
                    "EvalActionName": "s3:ListAllMyBuckets",
                    "EvalDecision": "allowed",
                },
            ],
            "IsTruncated": False,
        }
    )

    with (
        patch(
            "aws.probe.probe.initialize_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.clear_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.get_all_account_sessions",
            return_value=_accounts(({"Id": "111122223333", "Name": "A"}, session)),
        ),
        patch(
            "aws.probe.probe.get_allowed_regions",
            new_callable=AsyncMock,
            return_value=["us-east-1"],
        ),
    ):
        # Act
        await AwsPermissionProbe(probe_context).run()

    # Assert
    by_kind = {check.kind: check for check in probe_context.checks}
    assert by_kind["AWS::EC2::Instance"].status is ProbeCheckStatus.FAILURE
    assert "ec2:DescribeInstances" in (by_kind["AWS::EC2::Instance"].message or "")
    assert by_kind["AWS::S3::Bucket"].status is ProbeCheckStatus.SUCCESS


@pytest.mark.asyncio
async def test_probe_marks_missing_simulate_iam_as_unknown(
    probe_context: ProbeContext,
) -> None:
    # Arrange
    probe_context.available_kinds = ["AWS::EC2::Instance"]
    session = make_session(
        context_keys_side_effect=client_error(
            "AccessDenied", "GetContextKeysForPrincipalPolicy"
        )
    )

    with (
        patch(
            "aws.probe.probe.initialize_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.clear_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.get_all_account_sessions",
            return_value=_accounts(({"Id": "111122223333", "Name": "A"}, session)),
        ),
        patch(
            "aws.probe.probe.get_allowed_regions",
            new_callable=AsyncMock,
            return_value=["us-east-1"],
        ),
    ):
        # Act
        await AwsPermissionProbe(probe_context).run()

    # Assert
    assert probe_context.status is ProbeStatus.IN_PROGRESS
    assert probe_context.checks[0].status is ProbeCheckStatus.UNKNOWN
    assert probe_context.checks[0].message == MISSING_SIMULATE_PERMISSIONS_MESSAGE


@pytest.mark.asyncio
async def test_probe_implicit_deny_fails_independently_of_allowed_kinds(
    probe_context: ProbeContext,
) -> None:
    # Arrange
    probe_context.available_kinds = ["AWS::EC2::Instance", "AWS::S3::Bucket"]
    session = make_session(
        simulate_response={
            "EvaluationResults": [
                {
                    "EvalActionName": "ec2:DescribeInstances",
                    "EvalDecision": "implicitDeny",
                },
                {
                    "EvalActionName": "s3:ListAllMyBuckets",
                    "EvalDecision": "allowed",
                },
            ],
            "IsTruncated": False,
        }
    )

    with (
        patch(
            "aws.probe.probe.initialize_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.clear_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.get_all_account_sessions",
            return_value=_accounts(({"Id": "111122223333", "Name": "A"}, session)),
        ),
        patch(
            "aws.probe.probe.get_allowed_regions",
            new_callable=AsyncMock,
            return_value=["us-east-1"],
        ),
    ):
        # Act
        await AwsPermissionProbe(probe_context).run()

    # Assert
    by_kind = {check.kind: check for check in probe_context.checks}
    assert by_kind["AWS::EC2::Instance"].status is ProbeCheckStatus.FAILURE
    assert by_kind["AWS::S3::Bucket"].status is ProbeCheckStatus.SUCCESS


@pytest.mark.asyncio
async def test_probe_unmapped_kind_is_unknown(probe_context: ProbeContext) -> None:
    # Arrange
    probe_context.available_kinds = ["AWS::Custom::Thing"]
    session = make_session()

    with (
        patch(
            "aws.probe.probe.initialize_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.clear_aws_account_sessions",
            new_callable=AsyncMock,
        ),
        patch(
            "aws.probe.probe.get_all_account_sessions",
            return_value=_accounts(({"Id": "111122223333", "Name": "A"}, session)),
        ),
        patch(
            "aws.probe.probe.get_allowed_regions",
            new_callable=AsyncMock,
            return_value=["us-east-1"],
        ),
        patch(
            "aws.probe.probe.simulate_principal_policy",
            new_callable=AsyncMock,
            return_value=SimulateOutcome(decisions={}),
        ),
    ):
        # Act
        await AwsPermissionProbe(probe_context).run()

    # Assert
    assert probe_context.checks[0].status is ProbeCheckStatus.UNKNOWN
    assert "No permission mapping" in (probe_context.checks[0].message or "")
