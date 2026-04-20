from typing import Any, Optional

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clickup.clients.http.clickup_client import ClickUpClient
from clickup.core.exporters.abstract_exporter import AbstractClickUpExporter


class TaskExporter(AbstractClickUpExporter[ClickUpClient]):
    """Exporter for ClickUp Tasks.

    Endpoint: GET /v2/list/{list_id}/task
    Returns: Paginated list of tasks (100 per page)

    Pagination: Page-based with `page` parameter (starts at 0),
    response includes `last_page` boolean.

    Reference: https://developer.clickup.com/reference/gettasks
    """

    async def get_paginated_resources(
        self,
        options: Optional[dict[str, Any]] = None,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all tasks across all lists.

        Args:
            options: Optional dict with:
                - list_id: Fetch tasks for specific list only
                - include_closed: Include closed tasks (default: False)
                - include_subtasks: Include subtasks (default: False)
                - archived: Include archived tasks (default: False)
        """
        options = options or {}
        list_id = options.get("list_id")
        include_closed = options.get("include_closed", False)
        include_subtasks = options.get("include_subtasks", False)
        include_archived = options.get("archived", False)

        task_params = {
            "include_closed": str(include_closed).lower(),
            "subtasks": str(include_subtasks).lower(),
            "archived": str(include_archived).lower(),
        }

        if list_id:
            async for batch in self._get_tasks_from_list(list_id, task_params):
                yield batch
        else:
            async for batch in self._get_all_tasks(task_params, include_archived):
                yield batch

    async def _get_tasks_from_list(
        self, list_id: str, params: dict[str, Any]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get tasks from a specific list with pagination."""
        logger.info(f"Fetching tasks for list {list_id}")

        async for tasks in self.client.send_paginated_request(
            f"/v2/list/{list_id}/task",
            params=params,
            data_key="tasks",
        ):
            for task in tasks:
                task["__list_id"] = list_id
            yield tasks

    async def _get_all_tasks(
        self, task_params: dict[str, Any], include_archived: bool
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get all tasks from all lists across all workspaces."""
        workspaces_response = await self.client.send_api_request("/v2/team")

        for team in workspaces_response.get("teams", []):
            ws_id = str(team["id"])
            logger.info(f"Fetching tasks from workspace {ws_id}")

            spaces_response = await self.client.send_api_request(
                f"/v2/team/{ws_id}/space",
                params={"archived": str(include_archived).lower()},
            )

            for space in spaces_response.get("spaces", []):
                space_id = str(space["id"])

                folderless_lists_response = await self.client.send_api_request(
                    f"/v2/space/{space_id}/list",
                    params={"archived": str(include_archived).lower()},
                )

                for lst in folderless_lists_response.get("lists", []):
                    list_id = str(lst["id"])
                    async for batch in self._get_tasks_from_list(list_id, task_params):
                        yield batch

                folders_response = await self.client.send_api_request(
                    f"/v2/space/{space_id}/folder",
                    params={"archived": str(include_archived).lower()},
                )

                for folder in folders_response.get("folders", []):
                    folder_id = str(folder["id"])

                    lists_response = await self.client.send_api_request(
                        f"/v2/folder/{folder_id}/list",
                        params={"archived": str(include_archived).lower()},
                    )

                    for lst in lists_response.get("lists", []):
                        list_id = str(lst["id"])
                        async for batch in self._get_tasks_from_list(
                            list_id, task_params
                        ):
                            yield batch

    async def get_single_resource(self, resource_id: str) -> Optional[dict[str, Any]]:
        """Get a single task by ID.

        Endpoint: GET /v2/task/{task_id}
        """
        response = await self.client.send_api_request(f"/v2/task/{resource_id}")
        return response if response else None
