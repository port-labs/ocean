from typing import Dict, Any, List, Type, cast

from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import (
    is_access_denied_exception,
    is_resource_not_found_exception,
)
from loguru import logger

import asyncio


class ListAccountsAction(Action):
    async def _execute(self, accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return account identifiers as-is, normalized for downstream actions."""
        return accounts


class ListParentsAction(Action):
    async def _execute(self, accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        For each account, fetch all parent IDs using the Organizations paginator.
        Returns a list of dicts, each with a 'ParentIds' key.
        """
        results: List[Dict[str, Any]] = []
        parent_results = await asyncio.gather(
            *(self._fetch_parents(acc) for acc in accounts),
            return_exceptions=True,
        )
        for idx, result in enumerate(parent_results):
            if isinstance(result, Exception):
                if is_access_denied_exception(result):
                    logger.warning(
                        f"Administrator or management account has been denied access to list parents for account {accounts[idx]['Id']}, {result}, skipping ..."
                    )
                    continue
                elif is_resource_not_found_exception(result):
                    logger.warning(
                        f"Failed to list parents for account {accounts[idx]['Id']}: {result}"
                    )
                    results.append({"Parents": []})
                else:
                    raise result
            results.append(cast(Dict[str, List[Dict[str, Any]]], result))
        return results

    async def _fetch_parents(
        self, account: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:

        parents: List[Dict[str, Any]] = []
        paginator = self.client.get_paginator("list_parents")
        async for page in paginator.paginate(ChildId=account["Id"]):
            parents.extend(page["Parents"])
        return {"Parents": parents}


class ListTagsForResourceAction(Action):
    async def _execute(self, accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tags_results = await asyncio.gather(
            *(self._fetch_tags(acc) for acc in accounts), return_exceptions=True
        )
        results = []
        for idx, result in enumerate(tags_results):
            if isinstance(result, Exception):
                if is_access_denied_exception(result):
                    logger.warning(
                        f"Administrator or management account has been denied access to list tags for account {accounts[idx]['Id']}, {result}, skipping ..."
                    )
                    continue
                elif is_resource_not_found_exception(result):
                    logger.warning(
                        f"Failed to list tags for account {accounts[idx]['Id']}: {result}"
                    )
                    continue
                else:
                    raise result

            results.append(cast(Dict[str, Any], result))
        return results

    async def _fetch_tags(
        self, account: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        tags = []
        paginator = self.client.get_paginator("list_tags_for_resource")
        async for page in paginator.paginate(ResourceId=account["Id"]):
            tags.extend(page["Tags"])
        return {"Tags": tags}


class OrganizationsAccountActionsMap(ActionMap):
    defaults: List[Type[Action]] = [
        ListAccountsAction,
    ]
    options: List[Type[Action]] = [
        ListParentsAction,
        ListTagsForResourceAction,
    ]

    def merge(self, include: List[str]) -> List[Type[Action]]:
        return self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
