import asyncio
from typing import Any, Dict, List, TYPE_CHECKING, Optional, TypedDict
from urllib.parse import quote_plus

import httpx
from loguru import logger
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.exceptions.port_defaults import DefaultsProvisionFailed
from port_ocean.log.sensetive import sensitive_log_filter

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import PortAppConfig


ORG_USE_PROVISIONED_DEFAULTS_FEATURE_FLAG = "USE_PROVISIONED_DEFAULTS"
INTEGRATION_POLLING_INTERVAL_INITIAL_SECONDS = 3
INTEGRATION_POLLING_INTERVAL_BACKOFF_FACTOR = 1.55
INTEGRATION_POLLING_RETRY_LIMIT = 30
CREATE_RESOURCES_PARAM_NAME = "integration_modes"
CREATE_RESOURCES_PARAM_VALUE = ["create_resources"]


class LogAttributes(TypedDict):
    ingestUrl: str


class MetricsAttributes(TypedDict):
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
        self._metrics_attributes: MetricsAttributes | None = None

    async def is_integration_provision_enabled(
        self, integration_type: str, should_raise: bool = True, should_log: bool = True
    ) -> bool:
        enabled_integrations = await self.get_provision_enabled_integrations(
            should_raise, should_log
        )
        return integration_type in enabled_integrations

    async def get_provision_enabled_integrations(
        self, should_raise: bool = True, should_log: bool = True
    ) -> List[str]:
        logger.info("Fetching provision enabled integrations")
        response = await self.client.get(
            f"{self.auth.api_url}/integration/provision-enabled",
            headers=await self.auth.headers(),
        )

        handle_port_status_code(response, should_raise, should_log)

        return response.json().get("integrations", [])

    async def _get_current_integration(self) -> httpx.Response:
        logger.info(f"Fetching integration with id: {self.integration_identifier}")
        response = await self.client.get(
            f"{self.auth.api_url}/integration/{self.integration_identifier}",
            headers=await self.auth.headers(),
        )
        return response

    async def get_current_integration(
        self,
        should_raise: bool = True,
        should_log: bool = True,
        has_provision_feature_flag: bool = False,
    ) -> dict[str, Any]:
        response = await self._get_current_integration()
        handle_port_status_code(response, should_raise, should_log)
        integration = response.json().get("integration", {})
        if integration.get("config", None) or not integration:
            return integration
        is_provision_enabled_for_integration = (
            integration.get("installationAppType", None)
            and (
                await self.is_integration_provision_enabled(
                    integration.get("installationAppType", ""),
                    should_raise,
                    should_log,
                )
            )
            and has_provision_feature_flag
        )

        if is_provision_enabled_for_integration:
            logger.info(
                "integration type is enabled, polling until provisioning is complete"
            )
            integration = (
                await self._poll_integration_until_default_provisioning_is_complete()
            )
        return integration

    async def get_log_attributes(self) -> LogAttributes:
        if self._log_attributes is None:
            response = await self.get_current_integration()
            self._log_attributes = response["logAttributes"]
        return self._log_attributes

    async def get_metrics_attributes(self) -> LogAttributes:
        if self._metrics_attributes is None:
            response = await self.get_current_integration()
            self._metrics_attributes = response["metricAttributes"]
        return self._metrics_attributes

    async def _poll_integration_until_default_provisioning_is_complete(
        self,
    ) -> Dict[str, Any]:
        attempts = 0
        current_interval_seconds = INTEGRATION_POLLING_INTERVAL_INITIAL_SECONDS

        while attempts < INTEGRATION_POLLING_RETRY_LIMIT:
            logger.info(
                f"Fetching created integration and validating config, attempt {attempts+1}/{INTEGRATION_POLLING_RETRY_LIMIT}",
                attempt=attempts,
            )
            response = await self._get_current_integration()
            integration_json = response.json()
            if integration_json.get("integration", {}).get("config", {}) != {}:
                return integration_json

            logger.info(
                f"Integration config is still being provisioned, retrying in {current_interval_seconds} seconds"
            )
            await asyncio.sleep(current_interval_seconds)

            attempts += 1
            current_interval_seconds = int(
                current_interval_seconds * INTEGRATION_POLLING_INTERVAL_BACKOFF_FACTOR
            )

        raise DefaultsProvisionFailed(INTEGRATION_POLLING_RETRY_LIMIT)

    async def create_integration(
        self,
        _type: str,
        changelog_destination: dict[str, Any],
        port_app_config: Optional["PortAppConfig"] = None,
        create_port_resources_origin_in_port: Optional[bool] = False,
    ) -> Dict[str, Any]:
        logger.info(f"Creating integration with id: {self.integration_identifier}")
        headers = await self.auth.headers()
        json = {
            "installationId": self.integration_identifier,
            "installationAppType": _type,
            "version": self.integration_version,
            "changelogDestination": changelog_destination,
            "config": {},
        }

        query_params = {}

        if create_port_resources_origin_in_port:
            query_params[CREATE_RESOURCES_PARAM_NAME] = CREATE_RESOURCES_PARAM_VALUE

        if port_app_config and not create_port_resources_origin_in_port:
            json["config"] = port_app_config.to_request()
        response = await self.client.post(
            f"{self.auth.api_url}/integration",
            headers=headers,
            json=json,
            params=query_params,
        )
        handle_port_status_code(response)
        if create_port_resources_origin_in_port:
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
        handle_port_status_code(response)
        return response.json()["integration"]

    async def post_integration_sync_metrics(
        self, metrics: list[dict[str, Any]]
    ) -> None:
        logger.debug("starting POST metrics request", metrics=metrics)
        metrics_attributes = await self.get_metrics_attributes()
        headers = await self.auth.headers()
        url = metrics_attributes["ingestUrl"] + "/syncMetrics"
        response = await self.client.post(
            url,
            headers=headers,
            json={
                "syncKindsMetrics": metrics,
            },
        )
        handle_port_status_code(response, should_log=False)
        logger.debug("Finished POST metrics request")

    async def put_integration_sync_metrics(self, kind_metrics: dict[str, Any]) -> None:
        logger.debug("starting PUT metrics request", kind_metrics=kind_metrics)
        metrics_attributes = await self.get_metrics_attributes()
        url = (
            metrics_attributes["ingestUrl"]
            + f"/syncMetrics/resync/{kind_metrics['eventId']}/kind/{kind_metrics['kindIdentifier']}"
        )
        headers = await self.auth.headers()
        response = await self.client.put(
            url,
            headers=headers,
            json={
                "syncKindMetrics": kind_metrics,
            },
        )
        handle_port_status_code(response, should_log=False)
        logger.debug("Finished PUT metrics request")

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
        handle_port_status_code(response, should_log=False)
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
        handle_port_status_code(response, should_log=should_log)
        logger.debug(f"Examples for kind {kind} successfully ingested")

    async def _delete_current_integration(self) -> httpx.Response:
        logger.info(f"Deleting integration with id: {self.integration_identifier}")
        response = await self.client.delete(
            f"{self.auth.api_url}/integration/{self.integration_identifier}",
            headers=await self.auth.headers(),
        )
        return response

    async def delete_current_integration(
        self, should_raise: bool = True, should_log: bool = True
    ) -> dict[str, Any]:
        response = await self._delete_current_integration()
        handle_port_status_code(response, should_raise, should_log)
        return response.json()
