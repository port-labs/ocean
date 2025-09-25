from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from loguru import logger
import asyncio


class ListFunctionsAction(Action):
    """List Lambda functions as a pass-through function."""

    async def _execute(self, functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return Lambda functions as is"""
        return functions


class ListTagsAction(Action):
    """Fetches tags for Lambda functions."""

    async def _execute(self, functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fetch detailed tag information for the Lambda functions."""

        tag_results = await asyncio.gather(
            *(self._fetch_tags(function) for function in functions),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, tag_result in enumerate(tag_results):
            if isinstance(tag_result, Exception):
                function_name = functions[idx].get("FunctionName", "unknown")
                logger.error(
                    f"Error fetching tags for Lambda function '{function_name}': {tag_result}"
                )
                continue
            results.extend(cast(list[dict[str, Any]], tag_result))
        logger.info(f"Successfully fetched tags for {len(functions)} Lambda functions")
        return results

    async def _fetch_tags(self, function: dict[str, Any]) -> list[dict[str, Any]]:
        response = await self.client.list_tags(Resource=function["FunctionArn"])
        return [{"Tags": response["Tags"]}]


class LambdaFunctionActionsMap(ActionMap):
    defaults: list[Type[Action]] = [
        ListFunctionsAction,
    ]
    options: list[Type[Action]] = [
        ListTagsAction,
    ]
