from unittest import mock

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


def setup_ocean_context() -> None:
    try:
        mock_ocean_app = mock.MagicMock()
        mock_ocean_app.config.integration.config = {
            "app_host": "http://gitlab.com/api/v4",
            "gitlab_token": "tokentoken",
            "gitlab_url": "http://gitlab.com/api/v4",
            "webhook_secret": "secretsecret",
        }
        mock_ocean_app.integration_router = mock.MagicMock()
        mock_ocean_app.port_client = mock.MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass
