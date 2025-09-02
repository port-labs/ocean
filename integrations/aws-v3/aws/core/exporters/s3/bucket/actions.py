from typing import Dict, Any, List, Type


from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class GetBucketPublicAccessBlockAction(Action):
    async def _execute(self, bucket_names: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for bucket_name in bucket_names:
            response = await self.client.get_public_access_block(Bucket=bucket_name)  # type: ignore
            logger.info(
                f"Successfully fetched bucket public access block for bucket {bucket_name}"
            )
            results.append({
                "PublicAccessBlockConfiguration": response["PublicAccessBlockConfiguration"]
            })
        return results


class GetBucketOwnershipControlsAction(Action):
    async def _execute(self, bucket_names: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for bucket_name in bucket_names:
            response = await self.client.get_bucket_ownership_controls(Bucket=bucket_name)  # type: ignore[attr-defined]
            logger.info(
                f"Successfully fetched bucket ownership controls for bucket {bucket_name}"
            )
            results.append({"OwnershipControls": response.get("OwnershipControls", {})})
        return results


class GetBucketEncryptionAction(Action):
    async def _execute(self, bucket_names: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for bucket_name in bucket_names:
            response = await self.client.get_bucket_encryption(Bucket=bucket_name)  # type: ignore
            logger.info(f"Successfully fetched bucket encryption for bucket {bucket_name}")
            results.append({"BucketEncryption": response["ServerSideEncryptionConfiguration"]})
        return results


class GetBucketLocationAction(Action):
    async def _execute(self, bucket_names: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for bucket_name in bucket_names:
            response = await self.client.get_bucket_location(Bucket=bucket_name)  # type: ignore
            logger.info(f"Successfully fetched bucket location for bucket {bucket_name}")
            results.append({"BucketRegion": response["LocationConstraint"]})
        return results


class GetBucketArnAction(Action):
    async def _execute(self, bucket_names: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for bucket_name in bucket_names:
            bucket_arn = f"arn:aws:s3:::{bucket_name}"
            logger.info(f"Constructed bucket ARN for bucket {bucket_name}")
            results.append({"BucketArn": bucket_arn})
        return results


class GetBucketTaggingAction(Action):
    async def _execute(self, bucket_names: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for bucket_name in bucket_names:
            try:
                response = await self.client.get_bucket_tagging(Bucket=bucket_name)  # type: ignore
                logger.info(f"Successfully fetched bucket tagging for bucket {bucket_name}")
                results.append({"Tags": response.get("TagSet", [])})
            except self.client.exceptions.ClientError as e:
                if e.response.get("Error", {}).get("Code") == "NoSuchTagSet":
                    logger.info(f"No tag set found for bucket {bucket_name}")
                    results.append({"Tags": []})
                else:
                    raise
        return results


class S3BucketActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        GetBucketTaggingAction,
        GetBucketLocationAction,
        GetBucketArnAction,
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
