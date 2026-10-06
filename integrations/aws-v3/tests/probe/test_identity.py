from unittest.mock import AsyncMock, patch

import pytest

from aws.probe.identity import get_policy_source_arn
from tests.probe.conftest import make_session


@pytest.mark.asyncio
async def test_get_policy_source_arn_maps_assumed_role_to_iam_role() -> None:
    # Arrange
    session = make_session(
        account_id="111122223333",
        caller_arn=(
            "arn:aws:sts::111122223333:assumed-role/PortOceanReadRole/session-name"
        ),
    )

    with patch(
        "aws.probe.identity.RegionHelper.get_custom_partition_region_or_none",
        new_callable=AsyncMock,
        return_value=None,
    ):
        # Act
        arn = await get_policy_source_arn(session)

    # Assert
    assert arn == "arn:aws:iam::111122223333:role/PortOceanReadRole"


@pytest.mark.asyncio
async def test_get_policy_source_arn_keeps_user_arn() -> None:
    # Arrange
    session = make_session(
        account_id="111122223333",
        caller_arn="arn:aws:iam::111122223333:user/alice",
    )

    with patch(
        "aws.probe.identity.RegionHelper.get_custom_partition_region_or_none",
        new_callable=AsyncMock,
        return_value=None,
    ):
        # Act
        arn = await get_policy_source_arn(session)

    # Assert
    assert arn == "arn:aws:iam::111122223333:user/alice"
