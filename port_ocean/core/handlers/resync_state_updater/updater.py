import datetime
from typing import Any, Literal
from port_ocean.clients.port.client import PortClient
from port_ocean.utils.misc import IntegrationStateStatus
from port_ocean.utils.time import get_next_occurrence
from port_ocean.context.ocean import ocean
from port_ocean.helpers.metric.metric import MetricType, MetricPhase


class ResyncStateUpdater:
    def __init__(self, port_client: PortClient, scheduled_resync_interval: int | None):
        self.port_client = port_client
        self.initiated_at = datetime.datetime.now(tz=datetime.timezone.utc)
        self.scheduled_resync_interval = scheduled_resync_interval

        # This is used to differ between integration changes that require a full resync and state changes
        # So that the polling event-listener can decide whether to perform a full resync or not
        # TODO: remove this once we separate the state from the integration
        self.last_integration_state_updated_at: str = ""

    def _calculate_next_scheduled_resync(
        self,
        interval: int | None = None,
        custom_start_time: datetime.datetime | None = None,
    ) -> str | None:
        if interval is None:
            return None
        return get_next_occurrence(
            interval * 60, custom_start_time or self.initiated_at
        ).isoformat()

    async def update_before_resync(
        self,
        interval: int | None = None,
        custom_start_time: datetime.datetime | None = None,
    ) -> None:
        _interval = interval or self.scheduled_resync_interval
        nest_resync = self._calculate_next_scheduled_resync(
            _interval, custom_start_time
        )
        state: dict[str, Any] = {
            "status": IntegrationStateStatus.Running.value,
            "lastResyncEnd": None,
            "lastResyncStart": datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat(),
            "nextResync": nest_resync,
            "intervalInMinuets": _interval,
        }

        integration = await self.port_client.update_integration_state(
            state, should_raise=False
        )
        if integration:
            self.last_integration_state_updated_at = integration["resyncState"][
                "updatedAt"
            ]

    async def update_after_resync(
        self,
        status: Literal[
            IntegrationStateStatus.Completed, IntegrationStateStatus.Failed
        ] = IntegrationStateStatus.Completed,
        interval: int | None = None,
        custom_start_time: datetime.datetime | None = None,
    ) -> None:
        _interval = interval or self.scheduled_resync_interval
        nest_resync = self._calculate_next_scheduled_resync(
            _interval, custom_start_time
        )
        state: dict[str, Any] = {
            "status": status.value,
            "lastResyncEnd": datetime.datetime.now(
                tz=datetime.timezone.utc
            ).isoformat(),
            "nextResync": nest_resync,
            "intervalInMinuets": _interval,
        }

        integration = await self.port_client.update_integration_state(
            state, should_raise=False
        )
        if integration:
            self.last_integration_state_updated_at = integration["resyncState"][
                "updatedAt"
            ]

        ocean.metrics.set_metric(
            name=MetricType.SUCCESS_NAME,
            labels=[ocean.metrics.current_resource_kind(), MetricPhase.RESYNC],
            value=int(status == IntegrationStateStatus.Completed),
        )

        await ocean.metrics.send_metrics_to_webhook(
            kind=ocean.metrics.current_resource_kind()
        )
        # await ocean.metrics.report_sync_metrics(
        #     kinds=[ocean.metrics.current_resource_kind()]
        # ) # TODO: uncomment this when end points are ready
