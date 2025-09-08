from typing import Dict, Any, List, Type, cast

from aws.core.interfaces.action import Action, ActionMap
from loguru import logger

import asyncio


class GetBucketPublicAccessBlockAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        public_access_blocks = await asyncio.gather(
            *(self._fetch_public_access_block(bucket) for bucket in buckets),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, pab_result in enumerate(public_access_blocks):
            if isinstance(pab_result, Exception):
                bucket_name = buckets[idx].get("Name", "unknown")
                logger.error(
                    f"Error fetching bucket public access block for bucket '{bucket_name}': {pab_result}"
                )
                continue
            results.append(cast(Dict[str, Any], pab_result))
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
        ownership_controls = await asyncio.gather(
            *(self._fetch_ownership_controls(bucket) for bucket in buckets),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, ownership_result in enumerate(ownership_controls):
            if isinstance(ownership_result, Exception):
                bucket_name = buckets[idx].get("Name", "unknown")
                logger.error(
                    f"Error fetching bucket ownership controls for bucket '{bucket_name}': {ownership_result}"
                )
                continue
            results.append(cast(Dict[str, Any], ownership_result))
        return results

    async def _fetch_ownership_controls(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.get_bucket_ownership_controls(
            Bucket=bucket["Name"]
        )
        logger.info(
            f"Successfully fetched bucket ownership controls for bucket {bucket['Name']}"
        )
        return {"OwnershipControls": response["OwnershipControls"]}


class GetBucketEncryptionAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        encryptions = await asyncio.gather(
            *(self._fetch_encryption(bucket) for bucket in buckets),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, encryption_result in enumerate(encryptions):
            if isinstance(encryption_result, Exception):
                bucket_name = buckets[idx].get("Name", "unknown")
                logger.error(
                    f"Error fetching bucket encryption for bucket '{bucket_name}': {encryption_result}"
                )
                continue
            results.append(cast(Dict[str, Any], encryption_result))
        return results

    async def _fetch_encryption(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.get_bucket_encryption(Bucket=bucket["Name"])
        logger.info(
            f"Successfully fetched bucket encryption for bucket {bucket['Name']}"
        )
        return {"BucketEncryption": response["ServerSideEncryptionConfiguration"]}


class GetBucketLocationAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        locations = await asyncio.gather(
            *(self._fetch_location(bucket) for bucket in buckets),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, location_result in enumerate(locations):
            if isinstance(location_result, Exception):
                bucket_name = buckets[idx].get("Name", "unknown")
                logger.error(
                    f"Error fetching bucket location for bucket '{bucket_name}': {location_result}"
                )
                continue
            results.append(cast(Dict[str, Any], location_result))
        return results

    async def _fetch_location(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        response = await self.client.get_bucket_location(Bucket=bucket["Name"])
        logger.info(f"Successfully fetched bucket location for bucket {bucket['Name']}")
        return {"LocationConstraint": response["LocationConstraint"]}


class ListBucketsAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for bucket in buckets:
            data = {
                "CreationDate": bucket[
                    "CreationDate"
                ],  # ensure that every detail of the datetime string is preserved no rounding up or down
                "BucketName": bucket["Name"],
                "Arn": f"arn:aws:s3:::{bucket['Name']}",
            }
            results.append(data)
        return results


class GetBucketTaggingAction(Action):
    async def _execute(self, buckets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        tagging_results = await asyncio.gather(
            *(self._fetch_tagging(bucket) for bucket in buckets), return_exceptions=True
        )
        for idx, tagging_result in enumerate(tagging_results):
            if isinstance(tagging_result, Exception):
                bucket_name = buckets[idx].get("Name", "unknown")
                logger.error(
                    f"Error fetching bucket tagging for bucket '{bucket_name}': {tagging_result}"
                )
                results.append({"Tags": []})
            else:
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
