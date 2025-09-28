from typing import Dict, Any, List, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio
import json


class GetQueueAttributesAction(Action):
    """Fetches detailed attributes for SQS queues."""

    async def _execute(self, queues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not queues:
            return []

        attributes = await asyncio.gather(
            *(self._fetch_queue_attributes(queue) for queue in queues),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, attr_result in enumerate(attributes):
            if isinstance(attr_result, Exception):
                queue_url = queues[idx].get("QueueUrl", "unknown")
                logger.error(
                    f"Error fetching queue attributes for queue '{queue_url}': {attr_result}"
                )
                continue
            results.append(cast(Dict[str, Any], attr_result))
        return results

    async def _fetch_queue_attributes(self, queue: Dict[str, Any]) -> Dict[str, Any]:
        # Get all attributes for the queue
        response = await self.client.get_queue_attributes(
            QueueUrl=queue["QueueUrl"],
            AttributeNames=["All"]
        )
        
        attributes = response.get("Attributes", {})
        logger.info(f"Successfully fetched attributes for queue {queue['QueueUrl']}")
        
        # Extract queue name from URL (last part after the last slash)
        queue_url = queue["QueueUrl"]
        queue_name = queue_url.split("/")[-1]
        
        # Build the ARN from the attributes or construct it
        queue_arn = attributes.get("QueueArn", "")
        if not queue_arn and "OwnerAWSAccountId" in attributes:
            # Construct ARN if not provided
            account_id = attributes["OwnerAWSAccountId"]
            # Extract region from queue URL
            region = queue_url.split(".")[1] if "." in queue_url else "us-east-1"
            queue_arn = f"arn:aws:sqs:{region}:{account_id}:{queue_name}"

        return {
            "QueueName": queue_name,
            "QueueUrl": queue_url,
            "Arn": queue_arn,
            "ApproximateNumberOfMessages": int(attributes.get("ApproximateNumberOfMessages", 0)),
            "ApproximateNumberOfMessagesNotVisible": int(attributes.get("ApproximateNumberOfMessagesNotVisible", 0)),
            "ApproximateNumberOfMessagesDelayed": int(attributes.get("ApproximateNumberOfMessagesDelayed", 0)),
            "CreatedTimestamp": attributes.get("CreatedTimestamp"),
            "LastModifiedTimestamp": attributes.get("LastModifiedTimestamp"),
            "VisibilityTimeoutSeconds": int(attributes.get("VisibilityTimeout", 30)),
            "MaxReceiveCount": int(attributes.get("MaxReceiveCount", 0)) if "MaxReceiveCount" in attributes else None,
            "MessageRetentionPeriod": int(attributes.get("MessageRetentionPeriod", 345600)),
            "DelaySeconds": int(attributes.get("DelaySeconds", 0)),
            "ReceiveMessageWaitTimeSeconds": int(attributes.get("ReceiveMessageWaitTimeSeconds", 0)),
            "KmsMasterKeyId": attributes.get("KmsMasterKeyId"),
            "KmsDataKeyReusePeriodSeconds": int(attributes.get("KmsDataKeyReusePeriodSeconds", 300)) if "KmsDataKeyReusePeriodSeconds" in attributes else None,
            "SqsManagedSseEnabled": attributes.get("SqsManagedSseEnabled") == "true" if "SqsManagedSseEnabled" in attributes else None,
            "FifoQueue": attributes.get("FifoQueue") == "true" if "FifoQueue" in attributes else False,
            "ContentBasedDeduplication": attributes.get("ContentBasedDeduplication") == "true" if "ContentBasedDeduplication" in attributes else None,
            "DeduplicationScope": attributes.get("DeduplicationScope"),
            "FifoThroughputLimit": attributes.get("FifoThroughputLimit"),
            "RedrivePolicy": json.loads(attributes["RedrivePolicy"]) if attributes.get("RedrivePolicy") else None,
            "RedriveAllowPolicy": json.loads(attributes["RedriveAllowPolicy"]) if attributes.get("RedriveAllowPolicy") else None,
        }


class GetQueueTagsAction(Action):
    """Fetches tags for SQS queues."""

    async def _execute(self, queues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not queues:
            return []

        tags = await asyncio.gather(
            *(self._fetch_queue_tags(queue) for queue in queues),
            return_exceptions=True,
        )

        results: List[Dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                queue_url = queues[idx].get("QueueUrl", "unknown")
                logger.error(
                    f"Error fetching tags for queue '{queue_url}': {tag_result}"
                )
                continue
            results.append(cast(Dict[str, Any], tag_result))
        return results

    async def _fetch_queue_tags(self, queue: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = await self.client.list_queue_tags(QueueUrl=queue["QueueUrl"])
            tags = []
            for key, value in response.get("Tags", {}).items():
                tags.append({"Key": key, "Value": value})
            logger.info(f"Successfully fetched tags for queue {queue['QueueUrl']}")
            return {"Tags": tags}
        except self.client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "AccessDenied":
                logger.info(f"Access denied for tags on queue {queue['QueueUrl']}")
                return {"Tags": []}
            else:
                raise


class ListQueuesAction(Action):
    """Processes the initial list of queues from AWS."""

    async def _execute(self, queues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for queue_url in queues:
            # queues here are just URLs from list_queues
            if isinstance(queue_url, str):
                queue_name = queue_url.split("/")[-1]
                data = {
                    "QueueUrl": queue_url,
                    "QueueName": queue_name,
                }
            else:
                # Handle case where queue_url might be a dict
                data = {
                    "QueueUrl": queue_url.get("QueueUrl", ""),
                    "QueueName": queue_url.get("QueueName", ""),
                }
            results.append(data)
        return results


class SqsQueueActionsMap(ActionMap):
    """Groups all actions for SQS queues."""
    
    defaults: List[Type[Action]] = [
        ListQueuesAction,
        GetQueueAttributesAction,
        GetQueueTagsAction,
    ]
    options: List[Type[Action]] = [
        # Add optional actions here if needed in the future
    ]