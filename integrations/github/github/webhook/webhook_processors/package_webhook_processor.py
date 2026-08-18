from typing import Any, cast

from loguru import logger

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.package_exporter import (
    GHCR_PACKAGE_TYPE,
    RestPackageExporter,
)
from github.core.options import SinglePackageOptions
from github.helpers.utils import ObjectKind
from github.webhook.events import PACKAGE_EVENTS
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from integration import GithubPackageConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


def is_ghcr_package(package: dict[str, Any]) -> bool:
    """Return True when the webhook package is a GHCR container image.

    REST list responses use `package_type: "container"`. Webhook payloads may
    send `package_type` as `"CONTAINER"` and/or `registry.type` as `"CONTAINER"`.
    Legacy `docker.pkg.github.com` packages (`package_type: docker`) are excluded.
    """
    package_type = str(package.get("package_type") or "").lower()
    if package_type == GHCR_PACKAGE_TYPE:
        return True
    registry = package.get("registry") or {}
    return str(registry.get("type") or "").lower() == GHCR_PACKAGE_TYPE


class PackageWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if event.headers.get("x-github-event") != "package":
            return False
        action = event.payload.get("action")
        return action in PACKAGE_EVENTS

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Accept org and user-owned package events, including those with no repository."""
        if not (event._original_request and await self._should_process_event(event)):
            return False

        owner_login = self._package_owner_login(event.payload)
        if not owner_login:
            return False

        identifier = self._signature_identifier(event.payload, owner_login)
        return await self._verify_webhook_signature(identifier, event._original_request)

    def _signature_identifier(self, payload: EventPayload, owner_login: str) -> str:
        repository = payload.get("repository")
        if (
            isinstance(repository, dict)
            and repository.get("full_name")
            and not payload.get("organization")
        ):
            return f"personal account: {repository['full_name']}"
        return owner_login

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PACKAGE]

    def _matches_visibility(
        self, package: dict[str, Any], expected_visibility: str | None
    ) -> bool:
        if not expected_visibility:
            return True
        visibility = package.get("visibility")
        if visibility is None:
            return True
        return visibility == expected_visibility

    async def validate_payload(self, payload: EventPayload) -> bool:
        package = payload.get("package")
        if not isinstance(package, dict) or not package.get("name"):
            return False
        return bool(self._package_owner_login(payload))

    def _package_owner_login(self, payload: EventPayload) -> str | None:
        organization = payload.get("organization") or {}
        if organization.get("login"):
            return str(organization["login"])

        package = payload.get("package") or {}
        owner = package.get("owner") or {}
        if owner.get("login"):
            return str(owner["login"])

        repository = payload.get("repository")
        if isinstance(repository, dict):
            repo_owner = repository.get("owner") or {}
            if repo_owner.get("login"):
                return str(repo_owner["login"])
        return None

    def _package_owner_type(self, payload: EventPayload) -> str:
        if payload.get("organization"):
            return "Organization"
        package = payload.get("package") or {}
        owner = package.get("owner") or {}
        return str(owner.get("type") or "User")

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        package = payload["package"]
        package_name = package["name"]
        organization = self._package_owner_login(payload)

        if not organization:
            logger.warning(
                f"Skipping package event {action} for {package_name}: "
                "could not determine package owner"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not is_ghcr_package(package):
            logger.info(
                f"Skipping non-GHCR package event {action} for {package_name} "
                f"from {organization}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        config = cast(GithubPackageConfig, resource_config)
        expected_visibility = config.selector.visibility
        if not self._matches_visibility(package, expected_visibility):
            logger.info(
                f"Skipping package event {action} for {package_name} from {organization}: "
                f"visibility {package.get('visibility')!r} does not match selector "
                f"{expected_visibility!r}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(
            f"Processing package event: {action} for {package_name} from {organization}"
        )

        rest_client = await create_github_client_for_org(organization)
        exporter = RestPackageExporter(rest_client)
        data_to_upsert = await exporter.get_resource(
            SinglePackageOptions(
                organization=organization,
                package_name=package_name,
                owner_type=self._package_owner_type(payload),
                include_versions=config.selector.include_versions,
            )
        )
        if not data_to_upsert:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not self._matches_visibility(data_to_upsert, expected_visibility):
            logger.info(
                f"Skipping package {package_name} from {organization}: "
                f"visibility {data_to_upsert.get('visibility')!r} does not match selector "
                f"{expected_visibility!r}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
