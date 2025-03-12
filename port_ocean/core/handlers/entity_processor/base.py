from abc import abstractmethod

from port_ocean.helpers.metric.utils import TimeMetric
import port_ocean.context.ocean

from loguru import logger
from port_ocean.core.handlers.base import BaseHandler
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import (
    RAW_ITEM,
    CalculationResult,
    EntitySelectorDiff,
)
from port_ocean.helpers.metric.metric import MetricType, MetricPhase


class BaseEntityProcessor(BaseHandler):
    """Abstract base class for processing and parsing entities.

    This class defines abstract methods for parsing raw entity data into entity diffs.

    Attributes:
        context (Any): The context to be used during entity processing.
    """

    @abstractmethod
    async def _parse_items(
        self,
        mapping: ResourceConfig,
        raw_data: list[RAW_ITEM],
        parse_all: bool = False,
        send_raw_data_examples_amount: int = 0,
    ) -> CalculationResult:
        pass

    @TimeMetric(MetricPhase.TRANSFORM)
    async def parse_items(
        self,
        mapping: ResourceConfig,
        raw_data: list[RAW_ITEM],
        parse_all: bool = False,
        send_raw_data_examples_amount: int = 0,
    ) -> CalculationResult:
        """Public method to parse raw entity data and map it to an EntityDiff.

        Args:
            mapping (ResourceConfig): The configuration for entity mapping.
            raw_data (list[RawEntity]): The raw data to be parsed.
            parse_all (bool): Whether to parse all data or just data that passed the selector.
            send_raw_data_examples_amount (bool): Whether to send example data to the integration service.

        Returns:
            EntityDiff: The parsed entity differences.
        """
        with logger.contextualize(kind=mapping.kind):
            if not raw_data:
                return CalculationResult(EntitySelectorDiff([], []), [])
            result = await self._parse_items(
                mapping, raw_data, parse_all, send_raw_data_examples_amount
            )
            port_ocean.context.ocean.ocean.metrics.get_metric(
                MetricType.INPUT_COUNT[0], [MetricPhase.LOAD]
            ).inc(len(raw_data))
            port_ocean.context.ocean.ocean.metrics.get_metric(
                MetricType.OBJECT_COUNT[0], [MetricPhase.LOAD]
            ).inc(len(result.entity_selector_diff.passed))
            port_ocean.context.ocean.ocean.metrics.get_metric(
                MetricType.FAILED_COUNT[0], [MetricPhase.LOAD]
            ).inc(len(result.entity_selector_diff.failed))
            port_ocean.context.ocean.ocean.metrics.get_metric(
                MetricType.ERROR_COUNT[0], [MetricPhase.LOAD]
            ).inc(len(result.errors))

            return result
