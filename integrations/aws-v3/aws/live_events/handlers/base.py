from abc import ABC, abstractmethod
from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean


class BaseLiveEventHandler(ABC):
    """
    Base class for per-kind live event handlers.

    Each subclass handles one AWS resource kind (EC2, ECS, Lambda, S3).
    The handler is responsible for:
      1. Extracting the resource identifier from the raw EventBridge event.
      2. Deciding whether to upsert or delete the entity in Port.
      3. Fetching full resource state via the existing exporters (for upserts).
    """

    kind: str  # e.g. "AWS::EC2::Instance"

    @abstractmethod
    async def handle(self, event: dict[str, Any], account_id: str, region: str) -> None:
        """
        Process a single EventBridge event for this resource kind.

        Args:
            event:      The full EventBridge event envelope (already parsed from SNS).
            account_id: AWS account ID extracted from the event.
            region:     AWS region extracted from the event.
        """
        ...

    async def _upsert(self, resource: dict[str, Any]) -> None:
        """Push a single resource dict to Port as an upsert."""
        if not resource:
            logger.warning(f"[{self.kind}] upsert called with empty resource, skipping")
            return
        await ocean.register_raw(self.kind, [resource])
        logger.info(f"[{self.kind}] upserted entity")

    async def _delete(self, identifier: str) -> None:
        """Delete an entity from Port by its identifier."""
        await ocean.unregister_raw(self.kind, [{"identifier": identifier}])
        logger.info(f"[{self.kind}] deleted entity identifier={identifier}")
