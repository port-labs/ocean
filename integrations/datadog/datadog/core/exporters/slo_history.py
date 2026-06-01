import datetime
import http
from typing import Any, Optional, TypedDict

import httpx
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.queue_utils import process_in_queue

from datadog.core.exporters.base import PaginatedExporter
from datadog.core.exporters.slo import SloExporter
from utils import (
    generate_time_windows_from_interval_days,
    get_start_of_the_day_in_seconds_x_day_back,
    get_start_of_the_month_in_seconds_x_months_back,
)


class SloHistoryOptions(TypedDict):
    timeframe: int
    concurrency: int
    period_of_time_in_months: int
    period_of_time_in_days: Optional[int]


def _resolve_start_timestamp(options: SloHistoryOptions) -> int:
    period_of_time_in_days = options.get("period_of_time_in_days")
    if period_of_time_in_days:
        logger.info(f"Fetching SLO histories for {period_of_time_in_days} days back")
        return get_start_of_the_day_in_seconds_x_day_back(period_of_time_in_days)

    period_of_time_in_months = options["period_of_time_in_months"]
    logger.info(f"Fetching SLO histories for {period_of_time_in_months} months back")
    return get_start_of_the_month_in_seconds_x_months_back(period_of_time_in_months)


class SloHistoryExporter(PaginatedExporter[SloHistoryOptions]):
    async def get_paginated_resources(
        self, options: SloHistoryOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get SLO histories from Datadog, iterating over all SLOs and time windows."""
        timeframe = options["timeframe"]
        concurrency = options["concurrency"]
        start_timestamp = _resolve_start_timestamp(options)

        timestamps = generate_time_windows_from_interval_days(
            timeframe, start_timestamp
        )

        slo_exporter = SloExporter(self.client)
        async for slos in slo_exporter.get_paginated_resources():
            for from_ts, to_ts in timestamps:
                histories = await process_in_queue(
                    [slo["id"] for slo in slos],
                    self._get_slo_history,
                    timeframe,
                    from_ts,
                    to_ts,
                    concurrency=concurrency,
                )
                yield [history for history in histories if history]

    async def _get_slo_history(
        self, slo_id: str, timeframe: int, from_ts: int, to_ts: int
    ) -> dict[str, Any]:
        url = f"{self.client.api_url}/api/v1/slo/{slo_id}/history"
        readable_from_ts = datetime.datetime.fromtimestamp(from_ts)
        readable_to_ts = datetime.datetime.fromtimestamp(to_ts)
        try:
            logger.info(
                f"Fetching SLO history for {slo_id} from {readable_from_ts} to {readable_to_ts} in time range of {timeframe} days"
            )
            result = await self.client.send_api_request(
                url, params={"from_ts": from_ts, "to_ts": to_ts}
            )
            return {**result.get("data"), "__timeframe": timeframe}
        except httpx.HTTPStatusError as err:
            if err.response.status_code == http.HTTPStatus.BAD_REQUEST:
                if (
                    "The timeframe is incorrect: slo from_ts must be"
                    in err.response.text
                ):
                    logger.info(
                        f"Slo {slo_id} has no history for the given timeframe {readable_from_ts}, {readable_to_ts} in time range of {timeframe} days"
                    )
                    return {}
                if (
                    "Queries ending outside the retention date are invalid"
                    in err.response.text
                ):
                    logger.info(
                        f"Slo {slo_id} has no history for the given timeframe {readable_from_ts}, {readable_to_ts} in time range of {timeframe} days"
                    )
                    return {}
            logger.info(
                f"Failed to fetch SLO history for {slo_id}: {err}, {err.response.text}, for the given timeframe {readable_from_ts}, {readable_to_ts} in time range of {timeframe} days"
            )
            return {}
