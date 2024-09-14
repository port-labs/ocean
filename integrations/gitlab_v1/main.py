from typing import Any, List, Dict
from port_ocean.context.ocean import ocean
from client import GitlabHandler
from loguru import logger



gitlab_handler: GitlabHandler = None


@ocean.on_resync()
async def on_resync(kind: str) -> List[Dict[str, Any]]:
    global gitlab_handler
    if not gitlab_handler:
        print("GitLab handler not initialized. Please check on_start function.")
        return []


    if kind == "gitlabGroup":
        return await gitlab_handler.fetch_groups()
    elif kind == "gitlabProject":
        return await gitlab_handler.fetch_projects()
    elif kind == "gitlabMergeRequest":
        return await gitlab_handler.fetch_merge_requests()
    elif kind == "gitlabIssue":
        return await gitlab_handler.fetch_issues()

    print(f"Unknown kind: {kind}")
    return []


@ocean.on_start()
async def on_start() -> None:
    global gitlab_handler

        # Initialize GitLab handler
    private_token = ocean.integration_config['token']

    logger.error(ocean.integration_config)


    if not private_token:
        logger.error("GitLab Token not provided in configuration")
        return

    try:
        gitlab_handler = GitlabHandler(private_token)
        logger.info("GitLab integration started and handler initialized")
    except Exception as e:
        logger.error(f"Failed to initialize GitLab handler: {str(e)}")
