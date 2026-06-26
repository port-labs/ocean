from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class DescribeLoadBalancersAction(Action[list[dict[str, Any]]]):
    """Pass-through action that returns the raw load balancer data."""

    async def _execute(
        self, load_balancers: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return load_balancers


class DescribeTagsAction(Action[list[dict[str, Any]]]):
    """Fetches tags for ELBv2 load balancers in batch."""

    async def _execute(
        self, load_balancers: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not load_balancers:
            return []

        # ELBv2 supports batch tag fetching (up to 20 ARNs per call)
        BATCH_SIZE = 20
        arns = [lb["LoadBalancerArn"] for lb in load_balancers]
        arn_to_tags: dict[str, list[dict[str, Any]]] = {}

        for i in range(0, len(arns), BATCH_SIZE):
            batch_arns = arns[i : i + BATCH_SIZE]
            try:
                response = await self.client.describe_tags(ResourceArns=batch_arns)
                for tag_description in response.get("TagDescriptions", []):
                    resource_arn = tag_description.get("ResourceArn", "")
                    arn_to_tags[resource_arn] = tag_description.get("Tags", [])
            except Exception as e:
                if is_recoverable_aws_exception(e):
                    logger.warning(
                        f"Skipping tags for load balancer batch starting at index {i}: {e}"
                    )
                    for arn in batch_arns:
                        arn_to_tags.setdefault(arn, [])
                else:
                    logger.error(
                        f"Error fetching tags for load balancer batch: {e}"
                    )
                    raise

        results: list[dict[str, Any]] = []
        for lb in load_balancers:
            arn = lb["LoadBalancerArn"]
            results.append({"Tags": arn_to_tags.get(arn, [])})

        logger.info(
            f"Successfully fetched tags for {len(load_balancers)} load balancers"
        )
        return results


class ElasticLoadBalancingV2ActionsMap(ActionMap[list[dict[str, Any]]]):
    """Groups all actions for ELBv2 load balancers."""

    defaults: list[Type[Action[list[dict[str, Any]]]]] = [
        DescribeLoadBalancersAction,
    ]
    options: list[Type[Action[list[dict[str, Any]]]]] = [
        DescribeTagsAction,
    ]
