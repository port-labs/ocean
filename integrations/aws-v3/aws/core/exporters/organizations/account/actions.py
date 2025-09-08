from typing import Dict, Any, List, Type

from aws.core.interfaces.action import Action, ActionMap
from loguru import logger

import asyncio


class ListAccountsAction(Action):
    async def _execute(self, accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Return account identifiers as-is, normalized for downstream actions.

        Expects each identifier to include either 'Id' or a compatible account dict.
        """
        return accounts


class ListParentsAction(Action):
    async def _execute(self, accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        results = await asyncio.gather(*(self._fetch_parents(acc) for acc in accounts))
        return results

    async def _fetch_parents(self, account: Dict[str, Any]) -> Dict[str, Any]:
        account_id = account.get("Id")
        if not account_id:
            return {"ParentIds": []}
        page_parent_ids: List[str] = []
        paginator = self.client.get_paginator("list_parents")
        async for page in paginator.paginate(ChildId=account_id):
            parent_ids = [p.get("Id") for p in page.get("Parents", [])]
            page_parent_ids.extend(pid for pid in parent_ids if pid)
        return {"ParentIds": page_parent_ids}


class ListTagsForResourceAction(Action):
    async def _execute(self, accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = await asyncio.gather(*(self._fetch_tags(acc) for acc in accounts))
        return results

    async def _fetch_tags(self, account: Dict[str, Any]) -> Dict[str, Any]:
        account_id = account.get("Id")
        if not account_id:
            return {"Tags": []}
        # Organizations' resource tagging requires ARN. Construct ARN per docs:
        # arn:aws:organizations::<management-account-id>:account/<root-or-ou-id>/<account-id>
        # However, list_tags_for_resource accepts only ResourceId (ID or ARN) depending on API.
        try:
            response = await self.client.list_tags_for_resource(ResourceId=account_id)
            tags = response.get("Tags", [])
        except Exception as e:
            logger.warning(f"Failed to list tags for account {account_id}: {e}")
            tags = []
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
