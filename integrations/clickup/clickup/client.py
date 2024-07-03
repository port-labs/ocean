from typing import Any, AsyncGenerator, List, Dict
import httpx
from loguru import logger
from port_ocean.context import event
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

PAGE_SIZE = 50

class ClickUpClient:
    def __init__(self, clickup_url: str, clickup_api_key: str) -> None:
        """
        Initializes an instance of the ClickUpClient class.

        Args:
            clickup_url (str): The base URL for the ClickUp API.
            clickup_api_key (str): The API key for authenticating requests to the ClickUp API.
        """
        self.clickup_url = clickup_url
        self.api_url = f"{self.clickup_url}/api/v2"
        self.api_key = clickup_api_key

        self.api_auth_header = {"Authorization": self.api_key}
        self.client = http_async_client
        self.client.headers.update(self.api_auth_header)
        self.client.timeout = httpx.Timeout(30)  # 30 seconds timeout for requests

    @staticmethod
    def parse_projects_from_folders(folders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extracts and flattens 'Projects' lists from a list of folders.

        Args:
            folders: A list of dictionaries representing folders with lists.

        Returns:
            A single list of project dictionaries extracted from folders named "Projects".
        """
        folder_with_projects = [folder["lists"] for folder in folders]
        flattened_projects = [project for sublist in folder_with_projects for project in sublist]
        return flattened_projects

    @staticmethod
    def parse_project(project: Dict[str, Any], team_id: str) -> Dict[str, Any]:
        """
        Adds team ID to a project dictionary.

        Args:
            project (dict): A dictionary representing a project.
            team_id (str): The team ID to which the project belongs.

        Returns:
            dict: The updated project dictionary with the team ID.
        """
        project["__team_id"] = team_id
        return project

    @staticmethod
    def _generate_base_req_params(page: int = 0) -> Dict[str, Any]:
        """
        Generates base request parameters for API calls.

        Args:
            page (int, optional): The page number for pagination. Defaults to 0.

        Returns:
            dict: A dictionary with pagination parameters.
        """
        return {"page": page}

    async def _get_teams(self) -> Dict[str, Any]:
        """
        Fetches a list of teams from the ClickUp API.

        Returns:
            dict: JSON response containing the list of teams.
        """
        response = await self.client.get(f"{self.api_url}/team")
        response.raise_for_status()
        return response.json()

    async def _get_spaces(self, team_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches a list of spaces for a given team from the ClickUp API.

        Args:
            team_id (str): The ID of the team.
            params (dict): Query parameters (e.g., pagination).

        Returns:
            dict: JSON response containing the list of spaces.
        """
        response = await self.client.get(f"{self.api_url}/team/{team_id}/space", params=params)
        response.raise_for_status()
        return response.json()

    async def _get_tasks(self, list_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches tasks from a specific list in the ClickUp API.

        Args:
            list_id (str): The ID of the list.
            params (dict): Query parameters for the API request.

        Returns:
            dict: JSON response containing the tasks.
        """
        response = await self.client.get(f"{self.api_url}/list/{list_id}/task", params=params)

        return response.json() if response else {"tasks": []}

    async def _get_folderless_projects(self, space_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches folderless projects for a given space from the ClickUp API.

        Args:
            space_id (str): The ID of the space.
            params (dict): Query parameters (e.g., pagination).

        Returns:
            dict: JSON response containing the list of folderless projects.
        """
        response = await self.client.get(f"{self.api_url}/space/{space_id}/list", params=params)

        return response.json() if response else {"lists": []}

    async def _get_folders(self, space_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches folders for a given space from the ClickUp API.

        Args:
            space_id (str): The ID of the space.
            params (dict): Query parameters (e.g., pagination).

        Returns:
            dict: JSON response containing the list of folders.
        """
        response = await self.client.get(f"{self.api_url}/space/{space_id}/folder", params=params)
        response.raise_for_status()
        return response.json()

    async def get_paginated_projects(
        self, space_id: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetches and yields paginated lists of projects for a given space.

        Args:
            space_id (str): The ID of the space.

        Yields:
            list[dict[str, Any]]: Lists of project dictionaries.
        """
        logger.info("Getting projects from ClickUp")

        params = self._generate_base_req_params()
        foldered_projects = ClickUpClient.parse_projects_from_folders(
            (await self._get_folders(space_id, params))["folders"]
        )
        folderless_projects = (await self._get_folderless_projects(space_id, params))["lists"]
        total_projects = folderless_projects + foldered_projects

        if not total_projects:
            logger.warning("Space query returned 0 projects")

        params["page_size"] = PAGE_SIZE
        page = 0
        while page * PAGE_SIZE < len(total_projects):
            logger.info(f"Current query position: page {page}")

            folder_response_list = (await self._get_folders(space_id, params))["folders"]
            folderless_projects = (await self._get_folderless_projects(space_id, params))["lists"]
            foldered_projects = ClickUpClient.parse_projects_from_folders(folder_response_list)

            projects = folderless_projects + foldered_projects
            yield projects
            page += 1

    async def get_paginated_teams(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetches and yields a list of teams from the ClickUp API.

        Yields:
            list[dict[str, Any]]: Lists of team dictionaries.
        """
        logger.info("Getting teams from ClickUp")
        total_teams = (await self._get_teams())["teams"]

        if not total_teams:
            logger.warning(
                "Team query returned 0 teams, did you provide the correct ClickUp API credentials?"
            )

        yield total_teams

    async def get_paginated_spaces(
        self, team_id: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetches and yields paginated lists of spaces for a given team.

        Args:
            team_id (str): The ID of the team.

        Yields:
            list[dict[str, Any]]: Lists of space dictionaries.
        """
        logger.info("Getting spaces from ClickUp")

        params = self._generate_base_req_params()
        total_spaces = (await self._get_spaces(team_id, params))["spaces"]

        if not total_spaces:
            logger.warning(
                "Space query returned 0 spaces, did you provide the correct ClickUp API credentials?"
            )

        params["page_size"] = PAGE_SIZE
        page = 0
        while page * PAGE_SIZE < len(total_spaces):
            logger.info(f"Current query position: page {page}")
            space_response_list = (await self._get_spaces(team_id, params))["spaces"]
            yield space_response_list
            page += 1

    async def get_paginated_tasks(
        self, list_id: str
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetches and yields paginated lists of tasks for a given list.

        Args:
            list_id (str): The ID of the list.

        Yields:
            list[dict[str, Any]]: Lists of task dictionaries.
        """
        logger.info("Getting tasks (issues) from ClickUp")

        params = self._generate_base_req_params()
        total_tasks = (await self._get_tasks(list_id, params))["tasks"]

        if not total_tasks:
            logger.warning(
                "Task query returned 0 tasks, did you provide the correct ClickUp API credentials and query parameters?"
            )

        params["page_size"] = PAGE_SIZE
        page = 0
        while page * PAGE_SIZE < len(total_tasks):
            logger.info(f"Current query position: page {page}")
            task_response_list = (await self._get_tasks(list_id, params))["tasks"]
            yield task_response_list
            page += 1
