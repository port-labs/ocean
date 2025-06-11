from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.mixins.blueprints import BlueprintClientMixin
from port_ocean.clients.port.mixins.entities import EntityClientMixin
from port_ocean.clients.port.mixins.integrations import IntegrationClientMixin
from port_ocean.clients.port.mixins.migrations import MigrationClientMixin
from port_ocean.clients.port.mixins.organization import OrganizationClientMixin
from port_ocean.clients.port.types import (
    KafkaCreds,
)
from port_ocean.clients.port.utils import (
    handle_port_status_code,
    get_internal_http_client,
)
from port_ocean.exceptions.clients import KafkaCredentialsNotFound
from typing import Any


class PortClient(
    EntityClientMixin,
    IntegrationClientMixin,
    BlueprintClientMixin,
    MigrationClientMixin,
    OrganizationClientMixin,
):
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        integration_identifier: str,
        integration_type: str,
        integration_version: str,
    ):
        self.api_url = f"{base_url}/v1"
        self.client = get_internal_http_client(self)
        self.auth = PortAuthentication(
            self.client,
            client_id,
            client_secret,
            self.api_url,
            integration_identifier,
            integration_type,
            integration_version,
        )
        EntityClientMixin.__init__(self, self.auth, self.client)
        IntegrationClientMixin.__init__(
            self, integration_identifier, integration_version, self.auth, self.client
        )
        BlueprintClientMixin.__init__(self, self.auth, self.client)
        MigrationClientMixin.__init__(self, self.auth, self.client)
        OrganizationClientMixin.__init__(self, self.auth, self.client)

    async def get_kafka_creds(self) -> KafkaCreds:
        logger.info("Fetching organization kafka credentials")
        response = await self.client.get(
            f"{self.api_url}/kafka-credentials", headers=await self.auth.headers()
        )
        if response.is_error:
            logger.error("Error getting kafka credentials")
        handle_port_status_code(response)

        credentials = response.json().get("credentials")

        if credentials is None:
            raise KafkaCredentialsNotFound("No kafka credentials found")

        return credentials

    async def get_org_id(self) -> str:
        logger.info("Fetching organization id")

        response = await self.client.get(
            f"{self.api_url}/organization", headers=await self.auth.headers()
        )
        if response.is_error:
            logger.error(f"Error getting organization id, error: {response.text}")
        handle_port_status_code(response)

        return response.json()["organization"]["id"]

    async def update_integration_state(
        self, state: dict[str, Any], should_raise: bool = True, should_log: bool = True
    ) -> dict[str, Any]:
        if should_log:
            logger.debug(f"Updating integration resync state with: {state}")
        response = await self.client.patch(
            f"{self.api_url}/integration/{self.integration_identifier}/resync-state",
            headers=await self.auth.headers(),
            json=state,
        )
        handle_port_status_code(response, should_raise, should_log)
        if response.is_success and should_log:
            logger.info("Integration resync state updated successfully")

        return response.json().get("integration", {})
