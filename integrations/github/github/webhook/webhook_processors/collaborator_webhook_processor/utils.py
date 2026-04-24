from typing import cast
from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults

from integration import GithubCollaboratorConfig


def skip_if_affiliation_filtered(
    resource_config: ResourceConfig,
) -> WebhookEventRawResults | None:

    selector = cast(GithubCollaboratorConfig, resource_config).selector
    affiliation = selector.affiliation

    if affiliation == "all":
        return None

    logger.warning(
        "Skipping collaborator live event processing because "
        f"`selector.affiliation` is set to '{affiliation}'. Live events do not "
        "support affiliation filtering; run a resync to apply the filter."
    )
    return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
