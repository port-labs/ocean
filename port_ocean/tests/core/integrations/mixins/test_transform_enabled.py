from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from port_ocean.core.integrations.mixins.utils import is_transform_enabled
from port_ocean.core.models import IntegrationFeatureFlag


class TestIsTransformEnabled:
    @pytest.mark.asyncio
    async def test_returns_true_when_all_conditions_met(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[IntegrationFeatureFlag.DATA_SOURCE_PROCESSOR_ENABLED]
            )
            mock_ocean.config.transform.enabled = True
            mock_ocean.config.transform.base_url = "http://localhost:3017"

            result = await is_transform_enabled()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_org_flag_missing(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.get_organization_feature_flags = AsyncMock(
                return_value=["SOME_OTHER_FLAG"]
            )
            mock_ocean.config.transform.enabled = True
            mock_ocean.config.transform.base_url = "http://localhost:3017"

            result = await is_transform_enabled()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_local_config_disabled(self) -> None:
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[IntegrationFeatureFlag.DATA_SOURCE_PROCESSOR_ENABLED]
            )
            mock_ocean.config.transform.enabled = False
            mock_ocean.config.transform.base_url = "http://localhost:3017"

            result = await is_transform_enabled()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_base_url_not_set(self) -> None:
        """base_url is no longer required by is_transform_enabled itself."""
        with patch(
            "port_ocean.core.integrations.mixins.utils.ocean"
        ) as mock_ocean:
            mock_ocean.port_client.get_organization_feature_flags = AsyncMock(
                return_value=[IntegrationFeatureFlag.DATA_SOURCE_PROCESSOR_ENABLED]
            )
            mock_ocean.config.transform.enabled = True
            mock_ocean.config.transform.base_url = None

            result = await is_transform_enabled()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_and_logs_warning_when_exception_raised(self) -> None:
        with (
            patch(
                "port_ocean.core.integrations.mixins.utils.ocean"
            ) as mock_ocean,
            patch(
                "port_ocean.core.integrations.mixins.utils.logger"
            ) as mock_logger,
        ):
            mock_ocean.port_client.get_organization_feature_flags = AsyncMock(
                side_effect=Exception("network error")
            )

            result = await is_transform_enabled()

        assert result is False
        mock_logger.warning.assert_called_once()
        assert "transform" in mock_logger.warning.call_args[0][0].lower()
