from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetQueueAttributesAction(Action):
    """Fetches detailed attributes for SQS queues."""

    async def _execute(self, queues: list[str]) -> list[dict[str, Any]]:

        attributes = await asyncio.gather(
            *(self._fetch_queue_attributes(queue) for queue in queues),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, attr_result in enumerate(attributes):
            if isinstance(attr_result, Exception):
                queue_url = queues[idx]
                if is_recoverable_aws_exception(attr_result):
                    logger.warning(
                        f"Skipping queue attributes for queue '{queue_url}': {attr_result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching queue attributes for queue '{queue_url}': {attr_result}"
                    )
                    raise attr_result
            results.append(cast(dict[str, Any], attr_result))
        logger.info(f"Successfully fetched attributes for {len(results)} SQS queues")
        return results

    async def _fetch_queue_attributes(self, queue: str) -> dict[str, Any]:
        response = await self.client.get_queue_attributes(
            QueueUrl=queue, AttributeNames=["All"]
        )
        logger.info(f"Successfully fetched attributes for queue {queue}")

        return response["Attributes"]


class GetQueueTagsAction(Action):
    """Fetches tags for SQS queues."""

    async def _execute(self, queues: list[str]) -> list[dict[str, Any]]:
        if not queues:
            return []

        tags = await asyncio.gather(
            *(self._fetch_queue_tags(queue) for queue in queues),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                queue_url = queues[idx]
                if is_recoverable_aws_exception(tag_result):
                    logger.warning(
                        f"Skipping tags for queue '{queue_url}': {tag_result}"
                    )
                    continue
                else:
                    logger.error(f"Error fetching tags for queue '{queue_url}'")
                    raise tag_result
            results.append(cast(dict[str, Any], tag_result))
        logger.info(f"Successfully fetched tags for {len(results)} SQS queues")
        return results

    async def _fetch_queue_tags(self, queue: str) -> dict[str, Any]:
        response = await self.client.list_queue_tags(QueueUrl=queue)
        logger.info(f"Successfully fetched tags for queue {queue}")

        # Return tags in the format expected by the model
        tags = response.get("Tags", {})
        return {"Tags": tags}


class ListQueuesAction(Action):
    """List queues as a pass-through function."""

    async def _execute(self, queues: list[str]) -> list[dict[str, Any]]:
        """Return queue URLs wrapped in dictionaries"""
        return [{"QueueUrl": queue_url} for queue_url in queues]


class SqsQueueActionsMap(ActionMap):
    """Groups all actions for SQS queues."""

    defaults: list[Type[Action]] = [
        ListQueuesAction,
        GetQueueAttributesAction
    ]
    options: list[Type[Action]] = [
        GetQueueTagsAction
    ]
