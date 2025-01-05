import asyncio
from typing import Any, Dict, TYPE_CHECKING, Optional, TypedDict
from urllib.parse import quote_plus

import httpx
from loguru import logger
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_status_code
from port_ocean.log.sensetive import sensitive_log_filter

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class LogAttributes(TypedDict):
    ingestUrl: str


class IntegrationClientMixin:
    def __init__(
        self,
        integration_identifier: str,
        integration_version: str,
        auth: PortAuthentication,
        client: httpx.AsyncClient,
    ):
        self.integration_identifier = integration_identifier
        self.integration_version = integration_version
        self.auth = auth
        self.client = client
        self._log_attributes: LogAttributes | None = None

    async def _get_current_integration(self) -> httpx.Response:
        logger.info(f"Fetching integration with id: {self.integration_identifier}")
        response = await self.client.get(
            f"{self.auth.api_url}/integration/{self.integration_identifier}",
            headers=await self.auth.headers(),
        )
        return response

    async def get_current_integration(
        self, should_raise: bool = True, should_log: bool = True
    ) -> dict[str, Any]:
        response = await self._get_current_integration()
        handle_status_code(response, should_raise, should_log)
        return response.json().get("integration", {})

    async def get_log_attributes(self) -> LogAttributes:
        if self._log_attributes is None:
            response = await self.get_current_integration()
            self._log_attributes = response["logAttributes"]
        return self._log_attributes

    async def _poll_integration_until_default_provisioning_is_complete(
        self,
        interval=15,
    ) -> Dict[str, Any]:
        response = await self._get_current_integration()
        response_json = response.json()
        config = response_json.get("integration", {}).get("config", {})
        if config != {}:
            return response_json

        logger.info(
            f"Still waiting for integration config to be ready, waiting {interval} seconds"
        )
        await asyncio.sleep(interval)

        # TODO: Ensure that get_integration isn't cached
        result = await self._poll_integration_until_default_provisioning_is_complete()

        return result

    async def create_integration(
        self,
        _type: str,
        changelog_destination: dict[str, Any],
        port_app_config: Optional["PortAppConfig"] = None,
        use_provisioned_defaults: Optional[bool] = False,
    ) -> dict:
        logger.info(f"Creating integration with id: {self.integration_identifier}")
        if use_provisioned_defaults:
            logger.info("Creating integration with `use_provisioned_defaults`")
        headers = await self.auth.headers()
        json = {
            "installationId": self.integration_identifier,
            "installationAppType": _type,
            "version": self.integration_version,
            "changelogDestination": changelog_destination,
            "config": {},
        }

        if use_provisioned_defaults:
            json["provisionEnabled"] = use_provisioned_defaults

        if port_app_config and not use_provisioned_defaults:
            json["config"] = port_app_config.to_request()
        response = await self.client.post(
            f"{self.auth.api_url}/integration", headers=headers, json=json
        )
        handle_status_code(response)
        if use_provisioned_defaults:
            result = (
                await self._poll_integration_until_default_provisioning_is_complete()
            )
            return result["integration"]
        return response.json()["integration"]

    async def patch_integration(
        self,
        _type: str | None = None,
        changelog_destination: dict[str, Any] | None = None,
        port_app_config: Optional["PortAppConfig"] = None,
    ) -> dict:
        logger.info(f"Updating integration with id: {self.integration_identifier}")
        headers = await self.auth.headers()
        json: dict[str, Any] = {}
        if _type:
            json["installationAppType"] = _type
        if changelog_destination:
            json["changelogDestination"] = changelog_destination
        if port_app_config:
            json["config"] = port_app_config.to_request()
        json["version"] = self.integration_version

        response = await self.client.patch(
            f"{self.auth.api_url}/integration/{self.integration_identifier}",
            headers=headers,
            json=json,
        )
        handle_status_code(response)
        return response.json()["integration"]

    async def ingest_integration_logs(self, logs: list[dict[str, Any]]) -> None:
        logger.debug("Ingesting logs")
        log_attributes = await self.get_log_attributes()
        headers = await self.auth.headers()
        response = await self.client.post(
            log_attributes["ingestUrl"],
            headers=headers,
            json={
                "logs": logs,
            },
        )
        handle_status_code(response, should_log=False)
        logger.debug("Logs successfully ingested")

    async def ingest_integration_kind_examples(
        self, kind: str, data: list[dict[str, Any]], should_log: bool = True
    ):
        logger.debug(f"Ingesting examples for kind: {kind}")
        headers = await self.auth.headers()
        response = await self.client.post(
            f"{self.auth.api_url}/integration/{quote_plus(self.integration_identifier)}/kinds/{quote_plus(kind)}/examples",
            headers=headers,
            json={
                "examples": sensitive_log_filter.mask_object(data, full_hide=True),
            },
        )
        handle_status_code(response, should_log=should_log)
        logger.debug(f"Examples for kind {kind} successfully ingested")
