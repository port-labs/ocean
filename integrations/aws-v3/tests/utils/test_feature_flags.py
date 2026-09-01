from unittest.mock import AsyncMock, patch

import pytest

from aws.utils.feature_flags import is_aws_v3_live_events_enabled
from port_ocean.core.models import IntegrationFeatureFlag


@pytest.mark.asyncio
async def test_is_aws_v3_live_events_enabled_when_flag_present() -> None:
    with patch(
        "aws.utils.feature_flags.ocean.port_client.get_organization_feature_flags",
        new=AsyncMock(return_value=[IntegrationFeatureFlag.AWS_V3_LIVE_EVENTS_ENABLED]),
    ):
        assert await is_aws_v3_live_events_enabled() is True


@pytest.mark.asyncio
async def test_is_aws_v3_live_events_enabled_when_flag_missing() -> None:
    with patch(
        "aws.utils.feature_flags.ocean.port_client.get_organization_feature_flags",
        new=AsyncMock(return_value=[]),
    ):
        assert await is_aws_v3_live_events_enabled() is False


@pytest.mark.asyncio
async def test_is_aws_v3_live_events_enabled_when_port_call_fails() -> None:
    with patch(
        "aws.utils.feature_flags.ocean.port_client.get_organization_feature_flags",
        new=AsyncMock(side_effect=RuntimeError("port unavailable")),
    ):
        assert await is_aws_v3_live_events_enabled() is False
