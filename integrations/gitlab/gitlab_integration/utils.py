from typing import List

import gitlab
from gitlab import Gitlab
from gitlab_integration.gitlab_service import GitlabService
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.exceptions.context import EventContextNotFoundError

RETRY_TRANSIENT_ERRORS = True


def generate_gitlab_client(host: str, token: str) -> Gitlab:
    try:
        gitlab_client = Gitlab(
            host, token, retry_transient_errors=RETRY_TRANSIENT_ERRORS
        )
        gitlab_client.auth()
        logger.info("Successfully authenticated using the provided private token")
    except gitlab.exceptions.GitlabAuthenticationError:
        gitlab_client = Gitlab(
            host, oauth_token=token, retry_transient_errors=RETRY_TRANSIENT_ERRORS
        )
        gitlab_client.auth()
        logger.info("Successfully authenticated using the provided OAuth2.0 token")

    return gitlab_client


def get_all_services() -> List[GitlabService]:
    logic_settings = ocean.integration_config
    all_tokens_services = []

    logger.info(
        f"Creating gitlab clients for {len(logic_settings['token_mapping'])} tokens"
    )
    for token, group_mapping in logic_settings["token_mapping"].items():
        gitlab_client = generate_gitlab_client(logic_settings["gitlab_host"], token)
        gitlab_service = GitlabService(
            gitlab_client, logic_settings["app_host"], group_mapping
        )
        all_tokens_services.append(gitlab_service)

    return all_tokens_services


def get_cached_all_services() -> List[GitlabService]:
    try:
        all_services = event.attributes.get("all_tokens_services")
        if not all_services:
            logger.info("Gitlab clients are not cached, creating them")
            all_services = get_all_services()
            event.attributes["all_tokens_services"] = all_services
        return all_services
    except EventContextNotFoundError:
        return get_all_services()


class ObjectKind:
    GROUP = "group"
    ISSUE = "issue"
    JOB = "job"
    MERGE_REQUEST = "merge-request"
    PIPELINE = "pipeline"
    PROJECT = "project"
    FOLDER = "folder"
    FILE = "file"
    GROUPWITHMEMBERS = "group-with-members"
    PROJECTWITHMEMBERS = "project-with-members"
