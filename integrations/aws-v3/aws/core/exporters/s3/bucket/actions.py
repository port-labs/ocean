from typing import Dict, Any, List, Type, cast
from datetime import datetime

from aws.core.interfaces.action import Action, ActionMap
from loguru import logger

import asyncio


class GetBucketPublicAccessBlockAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        results = await asyncio.gather(
            *(self._fetch_public_access_block(bucket) for bucket in buckets)
        )
        return results

    async def _fetch_public_access_block(
        self, bucket: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = await self.client.get_public_access_block(Bucket=bucket["Name"])
        logger.info(
            f"Successfully fetched bucket public access block for bucket {bucket['Name']}"
        )
        return {
            "PublicAccessBlockConfiguration": response["PublicAccessBlockConfiguration"]
        }


class GetBucketOwnershipControlsAction(Action):

    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = await asyncio.gather(
            *(self._fetch_ownership_controls(bucket) for bucket in buckets)
        )
        return results

    async def _fetch_ownership_controls(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.get_bucket_ownership_controls(
            Bucket=bucket["Name"]
        )
        logger.info(
            f"Successfully fetched bucket ownership controls for bucket {bucket['Name']}"
        )
        return {"OwnershipControls": response.get("OwnershipControls", {})}


class GetBucketEncryptionAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = await asyncio.gather(
            *(self._fetch_encryption(bucket) for bucket in buckets)
        )
        return results

    async def _fetch_encryption(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.get_bucket_encryption(Bucket=bucket["Name"])
        logger.info(
            f"Successfully fetched bucket encryption for bucket {bucket['Name']}"
        )
        return {"BucketEncryption": response["ServerSideEncryptionConfiguration"]}


class GetBucketLocationAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = await asyncio.gather(
            *(self._fetch_location(bucket) for bucket in buckets)
        )
        return results

    async def _fetch_location(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.get_bucket_location(Bucket=bucket["Name"])
        logger.info(f"Successfully fetched bucket location for bucket {bucket['Name']}")
        return {"LocationConstraint": response["LocationConstraint"]}


class ListBucketsAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for bucket in buckets:
            creation_date: datetime = bucket["CreationDate"]
            results.append(
                {
                    "CreationDate": creation_date.isoformat(),
                    "BucketName": bucket["Name"],
                    "Arn": f"arn:aws:s3:::{bucket['Name']}",
                }
            )
        return results


class GetBucketTaggingAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        tagging = await asyncio.gather(
            *(self._fetch_tagging(bucket) for bucket in buckets), return_exceptions=True
        )
        for tagging_result in tagging:
            if isinstance(tagging_result, Exception):
                raise tagging_result
            results.append(cast(Dict[str, Any], tagging_result))
        return results

    async def _fetch_tagging(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.get_bucket_tagging(Bucket=bucket["Name"])
            logger.info(
                f"Successfully fetched bucket tagging for bucket {bucket['Name']}"
            )
            return {"Tags": response.get("TagSet", [])}
        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchTagSet":
                logger.info(f"No tag set found for bucket {bucket['Name']}")
                return {"Tags": []}
            else:
                raise


class S3BucketActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        GetBucketTaggingAction,
        GetBucketLocationAction,
        ListBucketsAction,
    ]
    options: List[Type[Action]] = [
        GetBucketPublicAccessBlockAction,
        GetBucketOwnershipControlsAction,
        GetBucketEncryptionAction,
    ]

    def merge(self, include: List[str]) -> List[Type[Action]]:
        # Always include all defaults, and any options whose class name is in include
        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
