from unittest.mock import AsyncMock, patch

import pytest

from port_ocean.core.utils.utils import validate_integration_runtime
from port_ocean.clients.port.client import PortClient
from port_ocean.core.models import Runtime
from port_ocean.tests.helpers.port_client import get_port_client_for_integration
from port_ocean.exceptions.core import IntegrationRuntimeException


class TestValidateIntegrationRuntime:

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "requested_runtime, installation_type, should_raise",
        [
            (Runtime.Saas, "Saas", False),
            (Runtime.Saas, "SaasOauth2", False),
            (Runtime.Saas, "OnPrem", True),
            (Runtime.OnPrem, "OnPrem", False),
            (Runtime.OnPrem, "SaasOauth2", True),
        ],
    )
    @patch.object(PortClient, "get_current_integration", new_callable=AsyncMock)
    async def test_validate_integration_runtime(
        self,
        mock_get_current_integration: AsyncMock,
        requested_runtime: Runtime,
        installation_type: str,
        should_raise: bool,
    ) -> None:
        # Arrange
        port_client = get_port_client_for_integration(
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            integration_identifier="mock-integration-identifier",
            integration_type="mock-integration-type",
            integration_version="mock-integration-version",
            base_url="mock-base-url",
        )

        # Mock the return value of get_current_integration
        mock_get_current_integration.return_value = {
            "installationType": installation_type
        }

        # Act & Assert
        if should_raise:
            with pytest.raises(IntegrationRuntimeException):
                await validate_integration_runtime(port_client, requested_runtime)
        else:
            await validate_integration_runtime(port_client, requested_runtime)

        # Verify that get_current_integration was called once
        mock_get_current_integration.assert_called_once()

    @pytest.mark.parametrize(
        "requested_runtime, installation_type, expected",
        [
            (Runtime.Saas, "SaasOauth2", True),
            (Runtime.Saas, "OnPrem", False),
            (Runtime.OnPrem, "OnPrem", True),
            (Runtime.OnPrem, "SaasCloud", False),
        ],
    )
    def test_runtime_installation_compatibility(
        self, requested_runtime: Runtime, installation_type: str, expected: bool
    ) -> None:
        assert (
            requested_runtime.is_installation_type_compatible(installation_type)
            == expected
        )
