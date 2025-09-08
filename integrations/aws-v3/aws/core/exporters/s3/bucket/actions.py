from typing import Dict, Any, List, Type, Union
from aws.core.interfaces.action import (
    Action,
    BatchAction,
    ActionMap,
)
from loguru import logger


class GetBucketPublicAccessBlockAction(Action):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_public_access_block(Bucket=bucket_name)  # type: ignore
        logger.info(
            f"Successfully fetched bucket public access block for bucket {bucket_name}"
        )
        return {
            "Name": bucket_name,
            "PublicAccessBlockConfiguration": response[
                "PublicAccessBlockConfiguration"
            ],
        }


class GetBucketOwnershipControlsAction(Action):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_bucket_ownership_controls(Bucket=bucket_name)  # type: ignore
        logger.info(
            f"Successfully fetched bucket ownership controls for bucket {bucket_name}"
        )
        return {"Name": bucket_name, "OwnershipControls": response["OwnershipControls"]}


class GetBucketEncryptionAction(Action):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_bucket_encryption(Bucket=bucket_name)  # type: ignore
        logger.info(f"Successfully fetched bucket encryption for bucket {bucket_name}")
        return {
            "Name": bucket_name,
            "BucketEncryption": response["ServerSideEncryptionConfiguration"],
        }


class GetBucketLocationAction(Action):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_bucket_location(Bucket=bucket_name)  # type: ignore
        logger.info(f"Successfully fetched bucket location for bucket {bucket_name}")
        return {"Name": bucket_name, "BucketRegion": response["LocationConstraint"]}


class GetBucketArnAction(Action):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        bucket_arn = f"arn:aws:s3:::{bucket_name}"
        logger.info(f"Constructed bucket ARN for bucket {bucket_name}")
        return {"Name": bucket_name, "BucketArn": bucket_arn}


class GetBucketTaggingAction(Action):
    async def _execute(self, bucket_name: str) -> dict[str, Any]:
        try:
            response = await self.client.get_bucket_tagging(Bucket=bucket_name)  # type: ignore
            logger.info(f"Successfully fetched bucket tagging for bucket {bucket_name}")
            return {"Name": bucket_name, "Tags": response.get("TagSet", [])}
        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchTagSet":
                return {"Name": bucket_name, "Tags": []}
            raise


class S3BucketActionsMap(ActionMap):
    defaults: List[Type[Union[Action, BatchAction]]] = [
        GetBucketTaggingAction,
        GetBucketLocationAction,
        GetBucketArnAction,
    ]
    options: List[Type[Union[Action, BatchAction]]] = [
        GetBucketPublicAccessBlockAction,
        GetBucketOwnershipControlsAction,
        GetBucketEncryptionAction,
    ]

    def merge(self, include: List[str]) -> List[Type[Union[Action, BatchAction]]]:
        # Always include all defaults, and any options whose class name is in include
        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
