from abc import abstractmethod
from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError

from azure_integration.foundry.clients.client_factory import create_arm_deployments_client, create_foundry_client, create_project_connections_client
from azure_integration.foundry.helpers.catalog_sync import catalog_delete_stub, normalize_catalog_payload
from azure_integration.foundry.helpers.project_scope import (
    enrich_with_project,
    get_project_endpoint,
    project_endpoint_context,
)
from azure_integration.foundry.kinds import ObjectKind


def _project_endpoint_from_run(run: IntegrationRun) -> str:
    props = run.execution_properties or {}
    endpoint = props.get("projectEndpoint") or props.get("foundryProjectEndpoint")
    if isinstance(endpoint, str) and endpoint.strip():
        return endpoint.rstrip("/")
    raise ActionExecutionError(
        "projectEndpoint is required on Foundry actions (Foundry project data-plane URL)"
    )


class AbstractFoundryExecutor(AbstractExecutor):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = create_foundry_client()
        self.arm_deployments = create_arm_deployments_client()
        self.project_connections = create_project_connections_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return 0.0

    async def execute(self, run: IntegrationRun) -> None:
        with project_endpoint_context(_project_endpoint_from_run(run)):
            await self.execute_foundry(run)

    @abstractmethod
    async def execute_foundry(self, run: IntegrationRun) -> None:
        raise NotImplementedError

    @property
    def project_endpoint(self) -> str:
        return get_project_endpoint()

    async def _ensure_port_app_config(self) -> None:
        """Load mapping config on the action-run context before nesting HTTP_REQUEST."""
        await ocean.integration.port_app_config_handler.get_port_app_config(
            use_cache=False
        )

    async def register_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        await self.register_entities(kind, [raw], run)

    async def register_entities(
        self, kind: str, raws: list[dict[str, Any]], run: IntegrationRun
    ) -> None:
        if not raws:
            return
        try:
            batch = [
                enrich_with_project(normalize_catalog_payload(kind, raw)) for raw in raws
            ]
            await self._ensure_port_app_config()
            async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
                await ocean.register_raw(kind, batch)
        except Exception as error:
            message = (
                f"Failed to upsert {len(raws)} {kind} entit(y/ies) into the catalog "
                f"(continuing): {error}"
            )
            logger.warning(message)
            await ocean.port_client.post_run_log(
                run, message, level="WARNING", should_raise=False
            )

    async def unregister_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        await self.unregister_entities(kind, [raw], run)

    async def unregister_entities(
        self, kind: str, raws: list[dict[str, Any]], run: IntegrationRun
    ) -> None:
        if not raws:
            return
        try:
            batch = [
                enrich_with_project(normalize_catalog_payload(kind, raw)) for raw in raws
            ]
            await self._ensure_port_app_config()
            async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
                await ocean.unregister_raw(kind, batch)
        except Exception as error:
            message = (
                f"Failed to delete {len(raws)} {kind} entit(y/ies) from the catalog "
                f"(continuing): {error}"
            )
            logger.warning(message)
            await ocean.port_client.post_run_log(
                run, message, level="WARNING", should_raise=False
            )

    async def unregister_by_identifier(
        self, kind: str, identifier: str, run: IntegrationRun
    ) -> None:
        await self.unregister_entity(
            kind, catalog_delete_stub(kind, identifier), run
        )

    async def sync_agent_catalog(self, agent_id: str, run: IntegrationRun) -> None:
        """Fetch agent + versions from Foundry and upsert catalog without waiting for resync."""
        agent_payload = await self.client.send_api_request(
            self.client.build_url(self.project_endpoint, f"agents/{agent_id}"),
        )
        if not isinstance(agent_payload, dict) or not agent_payload:
            logger.warning(f"Could not load agent {agent_id} for catalog sync")
            return

        await self.register_entity(ObjectKind.AGENT, agent_payload, run)

        versions_payload = await self.client.send_api_request(
            self.client.build_url(
                self.project_endpoint, f"agents/{agent_id}/versions"
            ),
        )
        versions = self.client.items_from_payload(versions_payload)
        if not versions:
            latest = agent_payload.get("versions")
            if isinstance(latest, dict) and isinstance(latest.get("latest"), dict):
                versions = [latest["latest"]]

        if versions:
            version_rows = [{**version, "agent_id": agent_id} for version in versions]
            await self.register_entities(ObjectKind.AGENT_VERSION, version_rows, run)
