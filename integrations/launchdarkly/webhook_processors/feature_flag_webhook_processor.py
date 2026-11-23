from webhook_processors.launchdarkly_abstract_webhook_processor import (
    _LaunchDarklyAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from client import LaunchDarklyClient, ObjectKind
from loguru import logger
from webhook_processors.utils import (
    extract_project_key_from_endpoint,
    enrich_resource_with_project,
)


class FeatureFlagWebhookProcessor(_LaunchDarklyAbstractWebhookProcessor):
    """Processes feature flag-related webhook events from LaunchDarkly."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event header contains required FeatureFlag event type."""
        return event.payload.get("kind") == ObjectKind.FEATURE_FLAG

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FEATURE_FLAG, ObjectKind.FEATURE_FLAG_STATUS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the feature flag webhook event and return the raw results."""
        endpoint = payload["_links"]["canonical"]["href"]
        kind = payload["kind"]
        resource_config_kind = resource_config.kind

        logger.info(
            f"Processing webhook event for feature flag from endpoint: {endpoint} with kind: {resource_config_kind}"
        )

        # Extract common data
        project_key = extract_project_key_from_endpoint(endpoint, kind)
        feature_flag_key = endpoint.strip("/").split("/")[-1]
        feature_flag = {"key": feature_flag_key, "__projectKey": project_key}

        # Handle deletion events
        if self.is_deletion_event(payload):
            payload["_links"]["self"]["href"] = endpoint
            if resource_config_kind == ObjectKind.FEATURE_FLAG_STATUS:
                deleted_records = [
                    {
                        "__environmentKey": env_key,
                        **payload,
                    }
                    for env in payload["accesses"]
                    if (env_key := self._extract_environment_key(env["resource"]))
                    is not None
                ]
            else:
                deleted_records = [feature_flag]
                if getattr(
                    resource_config.selector, "include_environment_config", False
                ):
                    # The deleted flag has no configuration to fetch, but the event
                    # lists its environments. Provide them so that mappings using
                    # `itemsToParse: .environments | to_entries` can build the
                    # identifiers of the per-environment entities to delete.
                    deleted_records[0]["environments"] = {
                        env_key: {}
                        for env in payload.get("accesses", [])
                        if (env_key := self._extract_environment_key(env["resource"]))
                        is not None
                    }

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=deleted_records
            )

        # Handle update events
        client = LaunchDarklyClient.create_from_ocean_configuration()
        if resource_config_kind == ObjectKind.FEATURE_FLAG_STATUS:
            response = await client.get_feature_flag_status(
                project_key, feature_flag_key
            )
            response["__projectKey"] = project_key
            data_to_update = [
                {**response.copy(), "__environmentKey": env_key, **env_data}
                for env_key, env_data in response["environments"].items()
            ]
        else:
            data_to_update = [
                await enrich_resource_with_project(endpoint, kind, client)
            ]

        return WebhookEventRawResults(
            updated_raw_results=data_to_update,
            deleted_raw_results=[],
        )

    def _extract_environment_key(self, resource: str) -> str | None:
        """Extract the environment key from a LaunchDarkly resource string."""
        try:
            env_part = resource.split(":env/")[1]
            return env_part.split(":")[0]
        except (IndexError, AttributeError) as e:
            logger.warning(
                f"Failed to extract environment key from resource: {resource!r} - {e}"
            )
            return None
