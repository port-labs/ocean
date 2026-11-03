from collections import defaultdict

from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import WebhookEventRawResults
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.integrations.mixins.utils import (
    build_live_event_data_entry,
    send_raw_live_event,
)
from port_ocean.core.models import LakehouseDataEntry, LakehouseOperation


class LiveEventsMixin(HandlerMixin):

    async def sync_raw_results(self, webhook_events_raw_result: list[WebhookEventRawResults]) -> None:
        """Hand the webhook event raw results collected from multiple processors to the data-source-processor.

        All raw data is sent before mapping, the same way a resync sends all raw data regardless
        of selector or mapping results. Upserted and deleted items of the same webhook event and
        kind go in a single POST so the lakehouse can correlate them under one event id.

        Args:
            webhook_events_raw_result: List of WebhookEventRawResults objects to process
        """
        grouped_entries: dict[tuple[str, str], list[LakehouseDataEntry]] = defaultdict(list)
        resync_start_times = {}

        for webhook_event_raw_result in webhook_events_raw_result:
            if not webhook_event_raw_result.has_resource:
                continue
            event_id = webhook_event_raw_result._webhook_trace_id
            if not event_id:
                logger.warning("Skipping live event raw data - no trace_id available")
                continue
            resource = webhook_event_raw_result.resource
            resource_index = (
                webhook_event_raw_result.resource_index
                if webhook_event_raw_result.resource_index is not None
                else 0
            )
            key = (event_id, resource.kind)
            resync_start_times[key] = webhook_event_raw_result.created_at

            for items, operation in (
                (webhook_event_raw_result.updated_raw_results, LakehouseOperation.UPSERT),
                (webhook_event_raw_result.deleted_raw_results, LakehouseOperation.DELETE),
            ):
                if not items:
                    continue
                grouped_entries[key].append(
                    build_live_event_data_entry(
                        resource=resource,
                        resource_index=resource_index,
                        items=items,
                        operation=operation,
                    )
                )

        for (event_id, kind), data_entries in grouped_entries.items():
            await send_raw_live_event(
                event_id=event_id,
                kind=kind,
                resync_start_time=resync_start_times[(event_id, kind)],
                data_entries=data_entries,
            )
