from typing import List

from gitlab import Gitlab
from gitlab_integration.gitlab_service import GitlabService
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.exceptions.context import EventContextNotFoundError


def get_all_services() -> List[GitlabService]:
    logic_settings = ocean.integration_config
    all_tokens_services = []

    logger.info(
        f"Creating gitlab clients for {len(logic_settings['token_mapping'])} tokens"
    )
    for token, group_mapping in logic_settings["token_mapping"].items():
        gitlab_client = Gitlab(logic_settings["gitlab_host"], token)
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
