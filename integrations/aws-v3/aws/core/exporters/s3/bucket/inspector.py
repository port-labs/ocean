from aws.core.exporters.s3.bucket.builder import S3BucketBuilder
from aws.core.exporters.s3.bucket.actions import (
    GetBucketPublicAccessBlockAction,
    GetBucketOwnershipControlsAction,
    GetBucketEncryptionAction,
    GetBucketTaggingAction,
)
from aws.core.exporters.s3.bucket.models import S3Bucket
from loguru import logger
from aws.core.interfaces.action import IAction
from typing import List, Dict, Any
from aiobotocore.client import AioBaseClient
import asyncio


class S3BucketInspector:
    """A Facade for inspecting S3 buckets."""

    def __init__(self, client: AioBaseClient) -> None:
        self.actions: List[IAction] = [
            GetBucketPublicAccessBlockAction(client),
            GetBucketOwnershipControlsAction(client),
            GetBucketEncryptionAction(client),
            GetBucketTaggingAction(client),
        ]

    async def inspect(self, bucket_name: str, include: List[str]) -> S3Bucket:
        builder = S3BucketBuilder(bucket_name)
        results = await asyncio.gather(
            *(
                self._run_action(action, bucket_name)
                for action in self.actions
                if action.__class__.__name__ in include
            )
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
