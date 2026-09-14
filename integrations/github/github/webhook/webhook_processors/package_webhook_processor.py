from typing import Any, cast

from loguru import logger

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.package_exporter import (
    matching_package_strategy,
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


class PackageWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "package"
            and event.payload.get("action") in PACKAGE_EVENTS
        )

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

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        package = payload["package"]
        package_name = package["name"]
        org = self.get_webhook_payload_organization(payload)
        org_login = org["login"]
        config = cast(GithubPackageConfig, resource_config)
        strategy = matching_package_strategy(package, config.selector.package_types)

        if strategy is None:
            logger.info(
                f"Skipping package event {action} for {package_name} "
                f"from {org_login}: package type does not match selector "
                f"{config.selector.package_types!r}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not self._matches_visibility(package, config.selector.visibility):
            logger.info(
                f"Skipping package event {action} for {package_name} from {org_login}: "
                f"visibility {package.get('visibility')!r} does not match selector "
                f"{config.selector.visibility!r}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(
            f"Processing package event: {action} for {package_name} from {org_login}"
        )

        rest_client = await create_github_client_for_org(org_login)
        exporter = RestPackageExporter(rest_client)
        data_to_upsert = await exporter.get_resource(
            SinglePackageOptions(
                organization=org_login,
                package_name=package_name,
                org_type=org["type"],
                package_type=strategy.package_type,
                include_versions=config.selector.include_versions,
                max_versions=config.selector.max_versions,
            )
        )
        if not data_to_upsert:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
