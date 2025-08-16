from typing import Dict, Any, List, Type


from aws.core.interfaces.action import Action, ActionMap
from loguru import logger


class GetBucketPublicAccessBlockAction(Action):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_public_access_block(Bucket=bucket_name)  # type: ignore
        logger.info(
            f"Successfully fetched bucket public access block for bucket {bucket_name}"
        )
        return {
            "PublicAccessBlockConfiguration": response["PublicAccessBlockConfiguration"]
        }


class GetBucketOwnershipControlsAction(Action):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_bucket_ownership_controls(Bucket=bucket_name)  # type: ignore
        logger.info(
            f"Successfully fetched bucket ownership controls for bucket {bucket_name}"
        )
        return {"OwnershipControls": response["OwnershipControls"]}


class GetBucketEncryptionAction(Action):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        response = await self.client.get_bucket_encryption(Bucket=bucket_name)  # type: ignore
        logger.info(f"Successfully fetched bucket encryption for bucket {bucket_name}")
        return {"BucketEncryption": response["ServerSideEncryptionConfiguration"]}


class GetBucketTaggingAction(Action):
    async def _execute(self, bucket_name: str) -> dict[str, Any]:
        try:
            response = await self.client.get_bucket_tagging(Bucket=bucket_name)  # type: ignore
            logger.info(f"Successfully fetched bucket tagging for bucket {bucket_name}")
            return {"Tags": response.get("TagSet", [])}
        except self.client.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchTagSet":
                return {"Tags": []}
            raise


class GetBucketNameAction(Action):
    async def _execute(self, bucket_name: str) -> Dict[str, Any]:
        return {"BucketName": bucket_name}


class S3BucketActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        GetBucketNameAction,
    ]
    options: List[Type[Action]] = [
        GetBucketPublicAccessBlockAction,
        GetBucketOwnershipControlsAction,
        GetBucketEncryptionAction,
        GetBucketTaggingAction,
    ]

    def merge(self, include: List[str]) -> List[Type[Action]]:
        # Always include all defaults, and any options whose class name is in include
        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
