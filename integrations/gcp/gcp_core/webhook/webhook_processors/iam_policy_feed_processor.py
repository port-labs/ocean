from typing import Any, cast

from google.cloud.asset_v1 import IamPolicySearchResult
from google.iam.v1 import policy_pb2  # type: ignore[import-untyped]
from google.protobuf import json_format  # type: ignore[import-untyped]
from loguru import logger

from gcp_core.errors import AssetHasNoProjectAncestorError
from gcp_core.feed_event import (
    FeedContent,
    canonical_resource_name,
    get_project_name_from_ancestors,
)
from gcp_core.search.resource_searches import (
    list_asset_names_in_project,
    search_asset_names_in_project,
)
from gcp_core.overrides import GCPIamPolicySelector, ProtoConfig
from gcp_core.utils import AssetTypesWithSpecialHandling, parse_protobuf_message
from gcp_core.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class IamPolicyFeedProcessor(BaseWebhookProcessor):
    feed_content = FeedContent.IAM_POLICY

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [AssetTypesWithSpecialHandling.IAM_POLICY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        feed_event = await self._get_feed_event(payload)
        if feed_event is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        selector = cast(GCPIamPolicySelector, resource_config.selector)
        asset = feed_event.asset
        asset_type = asset.asset_type
        asset_name = asset.name

        if selector.policy_query:
            logger.info(
                f"Skipping real-time IAM policy event for {asset_name}: the feed delivers the whole "
                f"policy, and this resource sets policyQuery '{selector.policy_query}'."
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if asset_type not in selector.asset_types:
            logger.info(
                f"Skipping real-time IAM policy event for {asset_name}: {asset_type} is not in this "
                f"resource's assetTypes {selector.asset_types}."
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        ancestors = asset.ancestors
        asset_folders = [
            ancestor for ancestor in ancestors if ancestor.startswith("folders/")
        ]
        asset_organization = next(
            (
                ancestor
                for ancestor in ancestors
                if ancestor.startswith("organizations/")
            ),
            "",
        )

        try:
            asset_project = get_project_name_from_ancestors(ancestors)
        except AssetHasNoProjectAncestorError:
            logger.warning(
                f"Couldn't find project ancestor for asset {asset_name}. "
                "Other ancestor types are not supported yet."
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        # The identifier the feed used, which is what the free-text search matches on. It only
        # narrows the candidates; canonical_resource_name still has to anchor one of them.
        assets = await search_asset_names_in_project(
            asset_project, asset_type, asset_name.rsplit("/", 1)[-1]
        )
        resource_name = canonical_resource_name(asset_name, assets)

        if (
            resource_name is None
            and asset_type == AssetTypesWithSpecialHandling.PROJECT
        ):
            # A project is the one asset the free-text index does not hold under the number
            # the feed names it with, and a project scope holds exactly one project.
            assets = await list_asset_names_in_project(asset_project, asset_type)
            resource_name = canonical_resource_name(asset_name, assets)

        if resource_name is None:
            logger.warning(
                f"Couldn't match feed asset {asset_name} to a name searchAllIamPolicies returns. "
                "Its grants would land under a different identifier than the resync's, so the "
                "event is skipped and the next resync will pick the change up."
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        # parse_protobuf_message falls back to should_use_snake_case(), which reads the selector off
        # a resource context a webhook does not have, so it must be told. False is what the resync
        # computes here: GCPIamPolicySelector has no preserve_api_response_case_style.
        config = ProtoConfig(preserving_proto_field_name=False)

        def to_raw_item(policy: dict[str, Any]) -> dict[str, Any]:
            return parse_protobuf_message(
                IamPolicySearchResult(
                    resource=resource_name,
                    asset_type=asset_type,
                    project=asset_project,
                    folders=asset_folders,
                    organization=asset_organization,
                    policy=json_format.ParseDict(
                        policy, policy_pb2.Policy(), ignore_unknown_fields=True
                    ),
                ),
                config,
            )

        logger.info(
            f"Processing real-time IAM policy event for {asset_type}: {asset_name} in {asset_project}"
        )
        # The prior policy expands to the grants that existed before, and the live-events mixin
        # removes every one the new policy no longer yields.
        prior_policy = feed_event.prior_asset.iam_policy
        return WebhookEventRawResults(
            updated_raw_results=(
                [] if feed_event.deleted else [to_raw_item(asset.iam_policy or {})]
            ),
            deleted_raw_results=[to_raw_item(prior_policy)] if prior_policy else [],
        )
