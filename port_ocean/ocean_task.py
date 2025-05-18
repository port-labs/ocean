from typing import Any, Callable, Dict, Type

import port_ocean.helpers.metric.metric


from loguru import logger
from pydantic import BaseModel

from port_ocean.clients.port.client import PortClient
from port_ocean.config.settings import (
    IntegrationConfiguration,
)
from port_ocean.context.ocean import (
    PortOceanContext,
    initialize_port_ocean_context,
    ocean,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.log.sensetive import sensitive_log_filter
from port_ocean.version import __integration_version__


class OceanTask:
    def __init__(
        self,
        integration_class: Callable[[PortOceanContext], BaseIntegration] | None = None,
        config_factory: Type[BaseModel] | None = None,
        config_override: Dict[str, Any] | None = None,
    ):
        initialize_port_ocean_context(self)

        self.config = IntegrationConfiguration(
            # type: ignore
            _integration_config_model=config_factory,
            **(config_override or {}),
        )
        # add the integration sensitive configuration to the sensitive patterns to mask out
        sensitive_log_filter.hide_sensitive_strings(
            *self.config.get_sensitive_fields_data()
        )
        self.metrics = port_ocean.helpers.metric.metric.Metrics(
            metrics_settings=self.config.metrics,
            integration_configuration=self.config.integration,
        )

        self.port_client = PortClient(
            base_url=self.config.port.base_url,
            client_id=self.config.port.client_id,
            client_secret=self.config.port.client_secret,
            integration_identifier=self.config.integration.identifier,
            integration_type=self.config.integration.type,
            integration_version=__integration_version__,
        )
        self.integration = (
            integration_class(ocean) if integration_class else BaseIntegration(ocean)
        )

    def is_saas(self) -> bool:
        return self.config.runtime.is_saas_runtime

    def load_external_oauth_access_token(self) -> str | None:
        if self.config.oauth_access_token_file_path is not None:
            try:
                with open(self.config.oauth_access_token_file_path, "r") as f:
                    return f.read()
            except Exception:
                logger.debug(
                    "Failed to load external oauth access token from file",
                    file_path=self.config.oauth_access_token_file_path,
                )
        return None
