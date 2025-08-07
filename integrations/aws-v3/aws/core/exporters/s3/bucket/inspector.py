from aws.core.exporters.s3.bucket.builder import S3BucketBuilder
from aws.core.exporters.s3.bucket.models import S3Bucket
from loguru import logger
from aws.core.exporters.s3.bucket.actions import S3BucketActionsMap
from typing import List, Dict, Any
from aiobotocore.client import AioBaseClient
import asyncio
from aws.core.interfaces.action import IAction


class S3BucketInspector:
    """A Facade for inspecting S3 buckets."""

    def __init__(self, client: AioBaseClient) -> None:
        self.client = client
        self.actions_map = S3BucketActionsMap()

    async def inspect(self, bucket_name: str, include: List[str]) -> S3Bucket:
        builder = S3BucketBuilder(bucket_name)
        action_classes = self.actions_map.merge(include)
        actions_to_run: List[IAction] = [
            action_cls(self.client) for action_cls in action_classes
        ]

        results = await asyncio.gather(
            *(self._run_action(action, bucket_name) for action in actions_to_run)
        )

        for result in results:
            if result is not None:
                builder.with_data(result)

        return builder.build()

    async def _run_action(self, action: IAction, bucket_name: str) -> Dict[str, Any]:
        try:
            logger.info(
                f"Running action {action.__class__.__name__} for bucket {bucket_name}"
            )
            data = await action.execute(bucket_name)
        except Exception as e:
            logger.warning(f"{action.__class__.__name__} failed: {e}")
            return {}
        return data
