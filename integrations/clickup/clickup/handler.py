from loguru import logger
from clickup.client import ClickUpClient
from port_ocean.context.ocean import ocean

class ClickUpPortHandler:
    def __init__(self):
        self.client = self.get_clickup_client()

    def get_clickup_client(self):
        try:
            host = ocean.integration_config["clickup_host"]
            api_key = ocean.integration_config["clickup_api_key"]
            if not host or not api_key:
                raise ValueError("ClickUp host or API key is not configured properly.")
            return ClickUpClient(host, api_key)
        except KeyError as e:
            logger.error(f"Configuration key missing: {e}")
            raise

    async def fetch_teams(self):
        try:
            async for teams in self.client.get_teams():
                yield teams
        except Exception as e:
            logger.error(f"Failed to fetch teams: {e}")
            raise

    async def fetch_spaces(self, team_id: str):
        try:
            async for spaces in self.client.get_spaces(team_id):
                yield spaces
        except Exception as e:
            logger.error(f"Failed to fetch spaces for team {team_id}: {e}")
            raise

    async def fetch_projects(self, space_id: str, team_id: str):
        try:
            async for projects in self.client.get_projects(space_id):
                yield [{**project, "__team_id": team_id} for project in projects]
        except Exception as e:
            logger.error(f"Failed to fetch projects for space {space_id}: {e}")
            raise

    async def fetch_all_projects(self):
        async for teams in self.fetch_teams():
            for team in teams:
                team_id = team["id"]
                async for spaces in self.fetch_spaces(team_id):
                    logger.info(f"Received spaces batch with {len(spaces)} spaces for team {team_id}")
                    for space in spaces:
                        space_id = space["id"]
                        async for projects in self.fetch_projects(space_id, team_id):
                            yield projects, team_id

    async def fetch_issues(self):
        async for projects, _ in self.fetch_all_projects():
            for project in projects:
                project_id = project["id"]
                try:
                    async for tasks in self.client.get_paginated_tasks(project_id):
                        logger.info(f"Received task batch with {len(tasks)} tasks for project {project_id}")
                        yield tasks
                except Exception as e:
                    logger.error(f"Failed to fetch tasks for project {project_id}: {e}")
                    raise
