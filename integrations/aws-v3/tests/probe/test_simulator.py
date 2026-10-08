from unittest.mock import AsyncMock, patch

import pytest

from aws.probe.simulator import (
    MISSING_SIMULATE_PERMISSIONS_MESSAGE,
    simulate_principal_policy,
)
from tests.probe.conftest import client_error, make_session


@pytest.mark.asyncio
async def test_simulate_principal_policy_returns_decisions() -> None:
    # Arrange
    session = make_session(
        simulate_response={
            "EvaluationResults": [
                {
                    "EvalActionName": "ec2:DescribeInstances",
                    "EvalDecision": "allowed",
                }
            ],
            "IsTruncated": False,
        }
    )

    with patch(
        "aws.probe.simulator.RegionHelper.get_custom_partition_region_or_none",
        new_callable=AsyncMock,
        return_value=None,
    ):
        # Act
        outcome = await simulate_principal_policy(
            session,
            "arn:aws:iam::111122223333:role/PortOceanReadRole",
            ["ec2:DescribeInstances"],
            "eu-west-1",
        )

    # Assert
    assert outcome.decisions == {"ec2:DescribeInstances": "allowed"}
    assert outcome.missing_simulate_permission is False
    session._iam.simulate_principal_policy.assert_awaited()
    kwargs = session._iam.simulate_principal_policy.await_args.kwargs
    assert kwargs["ContextEntries"][0]["ContextKeyValues"] == ["eu-west-1"]
    session._iam.get_context_keys_for_principal_policy.assert_awaited_once_with(
        PolicySourceArn="arn:aws:iam::111122223333:role/PortOceanReadRole",
    )


@pytest.mark.asyncio
async def test_simulate_principal_policy_missing_permission() -> None:
    # Arrange
    session = make_session(
        context_keys_side_effect=client_error(
            "AccessDenied", "GetContextKeysForPrincipalPolicy"
        )
    )

    with patch(
        "aws.probe.simulator.RegionHelper.get_custom_partition_region_or_none",
        new_callable=AsyncMock,
        return_value=None,
    ):
        # Act
        outcome = await simulate_principal_policy(
            session,
            "arn:aws:iam::111122223333:role/PortOceanReadRole",
            ["ec2:DescribeInstances"],
            "us-east-1",
        )

    # Assert
    assert outcome.missing_simulate_permission is True
    assert outcome.error_message == MISSING_SIMULATE_PERMISSIONS_MESSAGE
