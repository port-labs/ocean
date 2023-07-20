from typing import List

from gitlab import Gitlab
from gitlab_integration.gitlab_service import GitlabService
from loguru import logger

from port_ocean.context.ocean import ocean


def get_all_services() -> List[GitlabService]:
    logic_settings = ocean.integration_config
    all_tokens_services = []

    logger.info(
        f"Creating gitlab clients for {len(logic_settings['tokenMapping'])} tokens"
    )
    for token, group_mapping in logic_settings["tokenMapping"].items():
        gitlab_client = Gitlab(logic_settings["gitlabHost"], token)
        gitlab_service = GitlabService(
            gitlab_client, logic_settings["appHost"], group_mapping
        )
        all_tokens_services.append(gitlab_service)

    return all_tokens_services


class ObjectKind:
    ISSUE = "issue"
    JOB = "job"
    MERGE_REQUEST = "mergeRequest"
    PIPELINE = "pipeline"
    PROJECT = "project"
