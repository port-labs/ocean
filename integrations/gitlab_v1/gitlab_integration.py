import yaml
from enum import StrEnum
from typing import Any, Dict, AsyncGenerator
from port_ocean.context.ocean import ocean
from client import GitlabHandler
from helpers.webhook_handler import WebhookHandler
from loguru import logger
import asyncio
import secrets


CONFIG_FILE_PATH = ocean.integration_config.get('GITLAB_CONFIG_FILE', 'gitlab_config.yaml')
WEBHOOK_SECRET = ocean.integration_config.get('webhook_secret')
SECRET_LENGTH = 32
WEBHOOK_URL = ocean.integration_config.get('app_host')


class ObjectKind(StrEnum):
    GROUP = "group"
    PROJECT = "project"
    MERGE_REQUEST = "merge_request"
    ISSUE = "issue"


ENDPOINT_MAPPING = {
    ObjectKind.GROUP: "groups",
    ObjectKind.PROJECT: "projects",
    ObjectKind.MERGE_REQUEST: "merge_requests",
    ObjectKind.ISSUE: "issues"
}


class GitLabIntegration:
    def __init__(self):
        self.gitlab_handlers = []
        self.webhook_handlers = []
        self.config = self.load_config()


    def load_config(self):
        with open(CONFIG_FILE_PATH, 'r') as config_file:
            return yaml.safe_load(config_file)


    async def initialize(self):
        gitlab_tokens = ocean.integration_config.get('gitlab_token', [])
        if not gitlab_tokens:
            raise ValueError("No GitLab Tokens provided in configuration")


        if isinstance(gitlab_tokens, str):
            gitlab_tokens = [gitlab_tokens]


        gitlab_tokens = [token for token in gitlab_tokens if token]


        logger.info(f"Initializing with {len(gitlab_tokens)} tokens")


        for token in gitlab_tokens:
            gitlab_handler = GitlabHandler(token, CONFIG_FILE_PATH)
            webhook_handler = WebhookHandler(gitlab_handler)
            self.gitlab_handlers.append(gitlab_handler)
            self.webhook_handlers.append(webhook_handler)


        logger.info(f"GitLab integration initialized with {len(self.gitlab_handlers)} handlers")


        await self.setup_webhooks()


    async def setup_webhooks(self):
        events = self.get_webhook_events()
        logger.info(f"Setting up webhooks with events: {events}")


        webhook_secret = WEBHOOK_SECRET or secrets.token_hex(SECRET_LENGTH)
        logger.info("Using generated webhook secret" if WEBHOOK_SECRET is None else "Using provided webhook secret")


        setup_tasks = []
        for webhook_handler in self.webhook_handlers:
            task = asyncio.create_task(webhook_handler.setup_group_webhooks(WEBHOOK_URL, webhook_secret, events))
            setup_tasks.append(task)


        try:
            await asyncio.gather(*setup_tasks)
            logger.info("Webhooks set up successfully for all GitLab instances")
        except Exception as e:
            logger.error(f"Failed to set up webhooks: {str(e)}")
            raise


    def get_webhook_events(self):
        return self.config.get('events', [])


    async def resync_resources(self, kind: ObjectKind) -> AsyncGenerator[Dict[str, Any], None]:
        endpoint = ENDPOINT_MAPPING.get(kind)
        if not endpoint:
            raise ValueError(f"Invalid ObjectKind: {kind}")


        for gitlab_handler in self.gitlab_handlers:
            try:
                async for item in gitlab_handler.get_paginated_resources(endpoint):
                    logger.info(f"Received {kind} resource from a handler")
                    yield item
            except Exception as e:
                logger.error(f"Error fetching {kind} resources from a handler: {str(e)}")


    async def handle_webhook_event(self, event_type: str, payload: Dict[str, Any]):
        handlers = {
            "push": self.handle_push_event,
            "tag_push": self.handle_tag_push_event,
            "issue": self.handle_issue_event,
            "note": self.handle_note_event,
            "merge_request": self.handle_merge_request_event,
            "wiki_page": self.handle_wiki_page_event,
            "pipeline": self.handle_pipeline_event,
            "job": self.handle_job_event,
            "deployment": self.handle_deployment_event,
            "feature_flag": self.handle_feature_flag_event,
            "release": self.handle_release_event,
            "project_token": self.handle_project_token_event,
            "group_token": self.handle_group_token_event,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(payload)
        else:
            logger.warning(f"Unhandled event type: {event_type}")


    async def handle_push_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id}: {str(e)}")


    async def handle_tag_push_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port after tag push")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id} after tag push: {str(e)}")


    async def handle_issue_event(self, payload: Dict[str, Any]):
        issue_id = payload.get("object_attributes", {}).get("id")
        project_id = payload.get("project", {}).get("id")
        if issue_id and project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    issue = await gitlab_handler.get_single_resource(f"projects/{project_id}/issues", str(issue_id))
                    await ocean.register_raw(ObjectKind.ISSUE, issue)
                    logger.info(f"Updated issue {issue_id} in Port")
                    break
                except Exception as e:
                    logger.error(f"Failed to update issue {issue_id}: {str(e)}")


    async def handle_merge_request_event(self, payload: Dict[str, Any]):
        mr_id = payload.get("object_attributes", {}).get("id")
        project_id = payload.get("project", {}).get("id")
        if mr_id and project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    mr = await gitlab_handler.get_single_resource(f"projects/{project_id}/merge_requests", str(mr_id))
                    await ocean.register_raw(ObjectKind.MERGE_REQUEST, mr)
                    logger.info(f"Updated merge request {mr_id} in Port")
                    break
                except Exception as e:
                    logger.error(f"Failed to update merge request {mr_id}: {str(e)}")


    async def handle_wiki_page_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port after wiki page event")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id} after wiki page event: {str(e)}")


    async def handle_pipeline_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port after pipeline event")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id} after pipeline event: {str(e)}")


    async def handle_job_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port after job event")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id} after job event: {str(e)}")


    async def handle_deployment_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port after deployment event")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id} after deployment event: {str(e)}")


    async def handle_feature_flag_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port after feature flag event")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id} after feature flag event: {str(e)}")


    async def handle_release_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port after release event")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id} after release event: {str(e)}")


    async def handle_project_token_event(self, payload: Dict[str, Any]):
        project_id = payload.get("project", {}).get("id")
        if project_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    project = await gitlab_handler.get_single_resource("projects", str(project_id))
                    await ocean.register_raw(ObjectKind.PROJECT, project)
                    logger.info(f"Updated project {project_id} in Port after project token event")
                    break
                except Exception as e:
                    logger.error(f"Failed to update project {project_id} after project token event: {str(e)}")


    async def handle_group_token_event(self, payload: Dict[str, Any]):
        group_id = payload.get("group", {}).get("id")
        if group_id:
            for gitlab_handler in self.gitlab_handlers:
                try:
                    group = await gitlab_handler.get_single_resource("groups", str(group_id))
                    await ocean.register_raw(ObjectKind.GROUP, group)
                    logger.info(f"Updated group {group_id} in Port after group token event")
                    break
                except Exception as e:
                    logger.error(f"Failed to update group {group_id} after group token event: {str(e)}")
