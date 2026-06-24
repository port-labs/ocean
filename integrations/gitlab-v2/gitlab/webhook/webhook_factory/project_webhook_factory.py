from loguru import logger

from gitlab.webhook.events import ProjectEvents
from gitlab.webhook.webhook_factory._base_webhook_factory import BaseWebhookFactory

MAINTAINER_ACCESS_LEVEL = 40


class ProjectWebHook(BaseWebhookFactory[ProjectEvents]):
    """Creates and manages GitLab project-level webhooks.

    Used for projects in personal namespaces (namespace.kind == "user") where
    group-level hooks are not available. Project hooks support the same events
    as group hooks minus group-only events (member, subgroup, project).

    See: https://docs.gitlab.com/api/projects/#add-hook-to-project
    """

    async def create_project_webhook(self, project_id: int | str) -> bool:
        project_webhook_url = f"{self._app_host}/integration/hook/{project_id}"

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
        """Create project-level webhooks for all projects in personal namespaces.

        Personal namespace projects (namespace.kind == "user") do not receive
        group-level webhook events, so they need project-level hooks instead.
        Requires at least Maintainer access to create a project hook.
        """
        logger.info("Creating project webhooks for personal namespace projects.")

        async for projects_batch in self._client.get_projects(
            params={"min_access_level": MAINTAINER_ACCESS_LEVEL}
        ):
            for project in projects_batch:
                if project.get("namespace", {}).get("kind") == "user":
                    await self.create_project_webhook(project["id"])

        logger.info(
            "Completed project webhooks creation for personal namespace projects."
        )

    def webhook_events(self) -> ProjectEvents:
        return ProjectEvents()
