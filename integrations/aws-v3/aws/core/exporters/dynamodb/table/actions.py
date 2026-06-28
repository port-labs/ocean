from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class DescribeTableAction(Action[list[str]]):
    """Fetches detailed information about DynamoDB tables."""

    async def _execute(self, table_names: list[str]) -> list[dict[str, Any]]:
        if not table_names:
            return []

        details = await asyncio.gather(
            *(self._fetch_table_details(table_name) for table_name in table_names),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        success_count = 0
        for idx, detail_result in enumerate(details):
            if isinstance(detail_result, Exception):
                table_name = table_names[idx]
                if is_recoverable_aws_exception(detail_result):
                    logger.warning(
                        f"Skipping table details for table '{table_name}': {detail_result}"
                    )
                    results.append({})
                    continue
                else:
                    logger.error(
                        f"Error fetching table details for table '{table_name}': {detail_result}"
                    )
                    raise detail_result
            results.append(cast(dict[str, Any], detail_result))
            success_count += 1
        logger.info(
            f"Successfully fetched details for {success_count} DynamoDB tables"
        )
        return results

    async def _fetch_table_details(self, table_name: str) -> dict[str, Any]:
        response = await self.client.describe_table(TableName=table_name)
        table = response.get("Table", {})
        logger.info(f"Successfully fetched details for DynamoDB table '{table_name}'")
        return table


class ListTagsOfResourceAction(Action[list[str]]):
    """Fetches tags for DynamoDB tables."""

    async def _execute(self, table_names: list[str]) -> list[dict[str, Any]]:
        if not table_names:
            return []

        tags = await asyncio.gather(
            *(self._fetch_table_tags(table_name) for table_name in table_names),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        success_count = 0
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                table_name = table_names[idx]
                if is_recoverable_aws_exception(tag_result):
                    logger.warning(
                        f"Skipping tags for table '{table_name}': {tag_result}"
                    )
                    results.append({})
                    continue
                else:
                    logger.error(
                        f"Error fetching tags for table '{table_name}': {tag_result}"
                    )
                    raise tag_result
            results.append(cast(dict[str, Any], tag_result))
            success_count += 1
        logger.info(
            f"Successfully fetched tags for {success_count} DynamoDB tables"
        )
        return results

    async def _fetch_table_tags(self, table_name: str) -> dict[str, Any]:
        # Tags require the table ARN; we first describe the table to get it
        describe_response = await self.client.describe_table(TableName=table_name)
        table_arn = describe_response.get("Table", {}).get("TableArn", "")

        if not table_arn:
            logger.warning(
                f"Could not retrieve ARN for DynamoDB table '{table_name}', skipping tags"
            )
            return {"Tags": []}

        response = await self.client.list_tags_of_resource(ResourceArn=table_arn)
        tags = response.get("Tags", [])
        logger.info(f"Successfully fetched tags for DynamoDB table '{table_name}'")
        return {"Tags": tags}


class ListTablesAction(Action[list[str]]):
    """Pass-through action for DynamoDB table names."""

    async def _execute(self, table_names: list[str]) -> list[dict[str, Any]]:
        """Return table names wrapped in dictionaries."""
        return [{"TableName": table_name} for table_name in table_names]


class DynamoDBTableActionsMap(ActionMap[list[str]]):
    """Groups all actions for DynamoDB tables."""

    defaults: list[Type[Action[list[str]]]] = [
        ListTablesAction,
        DescribeTableAction,
    ]
    options: list[Type[Action[list[str]]]] = [ListTagsOfResourceAction]
