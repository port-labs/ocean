import asyncio

from loguru import logger

from gitlab.webhook.events import ProjectEvents
from gitlab.webhook.webhook_factory._base_webhook_factory import BaseWebhookFactory


class ProjectWebHook(BaseWebhookFactory[ProjectEvents]):
    """Creates and manages GitLab project-level webhooks."""

    async def create_project_webhook(self, project_id: int | str) -> bool:
        project_webhook_url = self.build_integration_webhook_url()

        try:
            response = await self.create(
                project_webhook_url, f"projects/{project_id}/hooks"
            )

            if response:
                logger.info(
                    f"Project webhook created for project {project_id} "
                    f"with id {response.get('id')}"
                )
            else:
                logger.info(f"Project webhook already exists for project {project_id}")

            return True

        except Exception as exc:
            logger.error(f"Failed to create webhook for project {project_id}: {exc}")
            return False

    async def create_webhooks_for_personal_projects(self) -> None:
        """Create project-level webhooks for all projects in the authenticated user's personal namespace."""
        logger.info("Creating project webhooks for personal namespace projects.")

        async for projects_batch in self._client.get_personal_namespace_projects():
            await asyncio.gather(
                *(
                    self.create_project_webhook(project["id"])
                    for project in projects_batch
                )
            )

        logger.info(
            "Completed project webhooks creation for personal namespace projects."
        )

    def webhook_events(self) -> ProjectEvents:
        return ProjectEvents()
