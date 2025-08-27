from typing import Dict, Any, List, Type
from aws.core.interfaces.action import (
    Action,
    DataAction,
    APIAction,
    ActionMap,
)
from loguru import logger


class GetBucketPublicAccessBlockAction(APIAction):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_public_access_block(Bucket=bucket_name)  # type: ignore
        logger.info(
            f"Successfully fetched bucket public access block for bucket {bucket_name}"
        )
        return {
            "PublicAccessBlockConfiguration": response["PublicAccessBlockConfiguration"]
        }


class GetBucketOwnershipControlsAction(APIAction):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_bucket_ownership_controls(Bucket=bucket_name)  # type: ignore
        logger.info(
            f"Successfully fetched bucket ownership controls for bucket {bucket_name}"
        )
        return {"OwnershipControls": response["OwnershipControls"]}


class GetBucketEncryptionAction(APIAction):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_bucket_encryption(Bucket=bucket_name)  # type: ignore
        logger.info(f"Successfully fetched bucket encryption for bucket {bucket_name}")
        return {"BucketEncryption": response["ServerSideEncryptionConfiguration"]}


class GetBucketLocationAction(APIAction):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_bucket_location(Bucket=bucket_name)  # type: ignore
        logger.info(f"Successfully fetched bucket location for bucket {bucket_name}")
        return {"BucketRegion": response["LocationConstraint"]}


class GetBucketArnAction(DataAction):
    async def _transform_data(self, bucket_name: str) -> Dict[str, Any]:
        bucket_arn = f"arn:aws:s3:::{bucket_name}"
        logger.info(f"Constructed bucket ARN for bucket {bucket_name}")
        return {"BucketArn": bucket_arn}


class GetBucketTaggingAction(APIAction):
    async def _execute(self, bucket_name: str) -> dict[str, Any]:
        try:
            response = await self.client.get_bucket_tagging(Bucket=bucket_name)  # type: ignore
            logger.info(f"Successfully fetched bucket tagging for bucket {bucket_name}")
            return {"Tags": response.get("TagSet", [])}
        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchTagSet":
                return {"Tags": []}
            raise


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
