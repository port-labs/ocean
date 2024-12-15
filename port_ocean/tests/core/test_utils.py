import unittest
from unittest.mock import AsyncMock, patch

import pytest

from port_ocean.core.utils import validate_integration_runtime
from port_ocean.clients.port.client import PortClient
from port_ocean.core.models import Runtime
from port_ocean.exceptions.core import IntegrationRuntimeException


class TestValidateIntegrationRuntime(unittest.TestCase):

    @pytest.mark.parametrize(
        "requested_runtime, installation_type, should_raise",
        [
            (Runtime.Saas, "SaasOauth2", False),
            (Runtime.Saas, "OnPrem", True),
            (Runtime.OnPrem, "OnPrem", False),
            (Runtime.OnPrem, "SaasCloud", True),
        ],
    )
    @patch.object(PortClient, "get_current_integration", new_callable=AsyncMock)
    async def test_validate_integration_runtime(
        self,
        mock_get_current_integration,
        requested_runtime,
        installation_type,
        should_raise,
    ) -> None:
        # Arrange
        port_client = PortClient()

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

    def test_runtime_installation_compatibility(self) -> None:
        test_cases = [
            (Runtime.Saas, "SaasOauth2", True),
            (Runtime.Saas, "OnPrem", False),
            (Runtime.OnPrem, "OnPrem", True),
            (Runtime.OnPrem, "SaasCloud", False),
        ]

        for runtime, installation_type, expected in test_cases:
            with self.subTest(runtime=runtime, installation_type=installation_type):
                self.assertEqual(
                    runtime.is_installation_type_compatible(installation_type), expected
                )
