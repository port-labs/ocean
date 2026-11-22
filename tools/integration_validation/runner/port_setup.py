from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.core.models import CreatePortResourcesOrigin
from port_ocean.tests.helpers.port_client import (
    ensure_ocean_context_for_standalone_port_client,
)
from tools.integration_validation.runner.blueprint_rewrite import (
    blueprint_creation_stages,
    blueprint_deletion_layers,
)
from tools.integration_validation.runner.errors import (
    ValidationCliError,
    ValidationFailedError,
    ValidationSetupError,
)

MIGRATION_POLL_INTERVAL_SECONDS = 1
# `ocean sail` patches the real version onto the integration at startup.
PLACEHOLDER_INTEGRATION_VERSION = "0.0.0"


@dataclass(frozen=True)
class ScenarioPortPlan:
    scenario_name: str
    integration_identifier: str
    blueprints: list[dict[str, Any]]
    blueprint_renames: dict[str, str]
    kinds: list[str]
    port_app_config: dict[str, Any]


class ValidationPortClient(PortClient):
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        integration_identifier: str,
        integration_type: str,
    ) -> None:
        super().__init__(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            integration_identifier=integration_identifier,
            integration_type=integration_type,
            integration_version=PLACEHOLDER_INTEGRATION_VERSION,
        )
        self.integration_type = integration_type

    async def create_validation_integration(
        self, port_app_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Create the integration with a raw mapping so that integration-specific
        selector fields survive (``PortAppConfig`` would drop them).

        Any origin other than Default makes Ocean replace this mapping on startup.
        """
        response = await self.client.post(
            f"{self.auth.api_url}/integration",
            headers=await self.auth.headers(),
            json={
                "installationId": self.integration_identifier,
                "installationAppType": self.integration_type,
                "version": self.integration_version,
                "changelogDestination": {},
                "config": port_app_config,
                "actionsProcessingEnabled": False,
                "incrementalSyncEnabled": False,
                "createPortResourcesOrigin": CreatePortResourcesOrigin.Default.value,
            },
        )
        handle_port_status_code(response)
        return response.json()["integration"]

    async def mark_port_resources_initialized(self) -> None:
        """Make Ocean skip its default-resources setup entirely on startup."""
        await self.patch_integration(are_port_resources_initialized=True)

    async def delete_blueprint_with_entities(self, identifier: str) -> str | None:
        """Start deleting the blueprint and its entities.

        Returns the migration id, or None when the blueprint does not exist.
        """
        response = await self.client.delete(
            f"{self.auth.api_url}/blueprints/{identifier}/all-entities",
            headers=await self.auth.headers(),
            params={"delete_blueprint": "true"},
        )
        if response.status_code == 404:
            return None
        handle_port_status_code(response)
        return response.json().get("migrationId") or None

    async def delete_validation_integration(self) -> None:
        """Delete the integration; a missing integration counts as deleted."""
        response = await self._delete_current_integration()
        if response.status_code != 404:
            handle_port_status_code(response)


def create_port_client(
    integration_identifier: str, integration_type: str
) -> ValidationPortClient:
    ensure_ocean_context_for_standalone_port_client()
    return ValidationPortClient(
        base_url=os.environ["OCEAN__PORT__BASE_URL"].rstrip("/"),
        client_id=os.environ["OCEAN__PORT__CLIENT_ID"],
        client_secret=os.environ["OCEAN__PORT__CLIENT_SECRET"],
        integration_identifier=integration_identifier,
        integration_type=integration_type,
    )


async def prepare_scenario_port(
    client: ValidationPortClient, plan: ScenarioPortPlan
) -> None:
    """Create the run's blueprints, then the integration with the scenario mapping.

    Resources left by an earlier run of the scenario are removed first. On any
    failure, the scenario's resources are removed before raising.
    """
    stale = await teardown_scenario_port(client, plan)
    if stale:
        raise ValidationSetupError(
            f"Scenario '{plan.scenario_name}': could not remove resources left by "
            f"a previous run: {', '.join(stale)}"
        )
    try:
        await _create_blueprints(client, plan.blueprints)
        await client.create_validation_integration(plan.port_app_config)
        await client.mark_port_resources_initialized()
    except Exception as exc:
        leftovers = await teardown_scenario_port(client, plan)
        if isinstance(exc, httpx.HTTPStatusError):
            raise _port_error(plan.scenario_name, exc, leftovers) from exc
        raise


async def teardown_scenario_port(
    client: ValidationPortClient, plan: ScenarioPortPlan
) -> list[str]:
    """Delete the scenario's integration and blueprints (with their entities)
    when they exist.

    Returns descriptions of resources that could not be deleted.
    """
    leftovers: list[str] = []
    try:
        await client.delete_validation_integration()
    except httpx.HTTPError as exc:
        logger.warning(
            f"Could not delete integration {plan.integration_identifier}: {exc}"
        )
        leftovers.append(f"integration {plan.integration_identifier}")

    for layer in blueprint_deletion_layers(plan.blueprints):
        deleted = await asyncio.gather(
            *(
                _delete_blueprint_with_entities(client, identifier)
                for identifier in layer
            )
        )
        leftovers.extend(
            f"blueprint {identifier}"
            for identifier, was_deleted in zip(layer, deleted)
            if not was_deleted
        )
    return leftovers


async def _create_blueprints(
    client: ValidationPortClient, blueprints: list[dict[str, Any]]
) -> None:
    bare, *patch_stages = blueprint_creation_stages(blueprints)
    # Wait for every create before raising, so rollback cannot race one in flight.
    results = await asyncio.gather(
        *(client.create_blueprint(blueprint) for blueprint in bare),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, BaseException):
            raise result
    for stage in patch_stages:
        await asyncio.gather(
            *(
                client.patch_blueprint(blueprint["identifier"], blueprint)
                for blueprint in stage
            )
        )


async def _delete_blueprint_with_entities(
    client: ValidationPortClient, identifier: str
) -> bool:
    try:
        migration_id = await client.delete_blueprint_with_entities(identifier)
        if migration_id:
            migration = await client.wait_for_migration_to_complete(
                migration_id, interval=MIGRATION_POLL_INTERVAL_SECONDS
            )
            if "FAIL" in migration.status.upper():
                logger.warning(
                    f"Deleting blueprint {identifier} ended with {migration.status}"
                )
                return False
    except httpx.HTTPError as exc:
        logger.warning(f"Could not delete blueprint {identifier}: {exc}")
        return False
    return True


def _port_error(
    scenario_name: str, exc: httpx.HTTPStatusError, leftovers: list[str]
) -> ValidationCliError:
    request = exc.request
    message = (
        f"Scenario '{scenario_name}': Port rejected {request.method} {request.url.path} "
        f"({exc.response.status_code}): {exc.response.text}"
    )
    if leftovers:
        message += f". Could not roll back: {', '.join(leftovers)}"
    if exc.response.status_code in (401, 403):
        return ValidationSetupError(message)
    return ValidationFailedError(message)
