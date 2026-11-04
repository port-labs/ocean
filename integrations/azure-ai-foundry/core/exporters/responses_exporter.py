from __future__ import annotations

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.http.foundry_client import FoundryHttpClient
from clients.quota_client import create_quota_client
from core.exporters.abstract_exporter import AbstractFoundryExporter
from foundry_incremental import CONVERSATION_INCREMENTAL, RESPONSE_INCREMENTAL
from helpers.conversation_rollup import build_conversation_rollup, register_conversation_rollups
from helpers.conversation_sync import effective_conversation_cutoff
from helpers.project_scope import enrich_with_project, get_project_endpoint
from helpers.responses_catalog import normalize_foundry_response
from helpers.utils import region_from_project_endpoint


class ResponsesExporter(AbstractFoundryExporter[FoundryHttpClient]):
    """Foundry Responses API objects, related to conversations with rollup refresh."""

    async def get_paginated_resources(
        self,
        *,
        since_days: int | None = 365,
        **_options: object,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        response_cursor = active_incremental_cursor()
        response_cutoff = effective_conversation_cutoff(
            response_cursor, since_days=since_days
        )
        conversation_cutoff = effective_conversation_cutoff(None, since_days=since_days)
        conv_params = CONVERSATION_INCREMENTAL.merge_params({}, None)
        quota = create_quota_client()
        project_endpoint = get_project_endpoint()

        async for conv_page in paginate_with_strategy(
            self.client.send_cursor_paginated_request(
                project_endpoint,
                "openai/v1/conversations",
                params=conv_params,
            ),
            cursor=conversation_cutoff,
            strategy=CONVERSATION_INCREMENTAL,
        ):
            responses_batch: list[dict[str, object]] = []
            rollups_to_register: list[dict[str, object]] = []

            for conversation in conv_page:
                conversation_id = conversation.get("id")
                if not isinstance(conversation_id, str) or not conversation_id:
                    continue
                response_params = RESPONSE_INCREMENTAL.merge_params(
                    {"order": "desc", "conversation_id": conversation_id},
                    response_cursor,
                )
                touched = False

                async for response_page in paginate_with_strategy(
                    self.client.send_cursor_paginated_request(
                        project_endpoint,
                        "openai/v1/responses",
                        params=response_params,
                    ),
                    cursor=response_cutoff,
                    strategy=RESPONSE_INCREMENTAL,
                ):
                    for source in response_page:
                        response_row = normalize_foundry_response(source)
                        if not response_row:
                            continue
                        touched = True
                        responses_batch.append(
                            enrich_with_project(dict(response_row))
                        )

                if touched:
                    rollups_to_register.append(
                        await build_conversation_rollup(
                            self.client,
                            project_endpoint=project_endpoint,
                            conversation_id=conversation_id,
                            conversation_list_row=conversation,
                        )
                    )

            if not responses_batch:
                continue

            check = await quota.check_before_batch(
                region=region_from_project_endpoint(project_endpoint),
                batch_size=len(responses_batch),
            )
            if not check.allowed:
                logger.warning(
                    f"Skipping response batch for {project_endpoint}: {check.message}"
                )
                continue

            yield responses_batch
            await register_conversation_rollups(rollups_to_register)
