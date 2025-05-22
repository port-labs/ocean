import os
import typing as t
import dotenv
import logging
from github.client import GithubClient
from port_ocean.context.ocean import ocean
from fastapi import Request
from github.webhook import WebhookHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

dotenv.load_dotenv()

MAX_BATCH_SIZE = 100


@ocean.on_start()
async def startup() -> None:
    # verify env vars are set
    if not os.getenv("GITHUB_TOKEN"):
        raise ValueError("GITHUB_TOKEN is not set.")
    if not os.getenv("GITHUB_WEBHOOK_SECRET"):
        # raise ValueError("GITHUB_WEBHOOK_SECRET is not set.")
        logger.warning("GITHUB_WEBHOOK_SECRET is not set. Webhook will not be enabled/usable")


@ocean.on_resync("Repository")
async def resync_repository(
    kind: str,
) -> t.AsyncGenerator[list[dict[str, t.Any]], None]:
    logger.info(f"Starting repository resync for kind: {kind}")

    handler = GithubClient.from_env()

    try:
        repositories = await handler.get_repositories()
    except Exception as e:
        logger.error(f"Failed to fetch repositories: {str(e)}")
        return

    logger.info(f"Retrieved {len(repositories)} repositories")

    repository_count = len(repositories)
    for i in range(0, repository_count, MAX_BATCH_SIZE):
        batch = repositories[i : i + MAX_BATCH_SIZE]

        yield [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "full_name": r["full_name"],
                "private": r["private"],
                "url": r["html_url"],
                "fork": r["fork"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "pushed_at": r["pushed_at"],
                "size": r["size"],
                "stargazers_count": r["stargazers_count"],
            }
            for r in batch
        ]


@ocean.on_resync("PullRequest")
async def resync_pull_requests(
    kind: str,
) -> t.AsyncGenerator[list[dict[str, t.Any]], None]:
    logger.info(f"Starting pull request resync for kind: {kind}")

    handler = GithubClient.from_env()

    try:
        repositories = await handler.get_repositories()
    except Exception as e:
        logger.error(f"Failed to fetch repositories: {str(e)}")
        return

    logger.info(f"Retrieved {len(repositories)} repositories for PR sync")

    for repo in repositories:
        try:
            owner, repo_name = repo["full_name"].split("/")
            logger.info(f"Fetching PRs for repository: {repo_name}")
            prs = await handler.get_pull_requests(owner, repo_name)
            logger.info(f"Retrieved {len(prs)} PRs for {repo_name}")

            # Log PR statistics
            open_prs = sum(1 for pr in prs if pr["state"] == "open")
            closed_prs = sum(1 for pr in prs if pr["state"] == "closed")
            draft_prs = sum(1 for pr in prs if pr.get("draft", False))

            logger.info(
                f"PR statistics for {repo_name}: "
                f"Open: {open_prs}, Closed: {closed_prs}, Draft: {draft_prs}"
            )

            # Process PRs in batches
            processed_prs = [
                {
                    "id": str(pr["id"]),
                    "number": pr["number"],
                    "title": pr["title"],
                    "state": pr["state"],
                    "url": pr["html_url"],
                    "created_at": pr["created_at"],
                    "updated_at": pr["updated_at"],
                    "repository": repo["full_name"],
                    "author": pr["user"]["login"],
                    "draft": pr.get("draft", False),
                    "mergeable": pr.get("mergeable", False),
                    "mergeable_state": pr.get("mergeable_state", ""),
                }
                for pr in prs
            ]

            # Yield PRs in batches
            for i in range(0, len(processed_prs), MAX_BATCH_SIZE):
                yield processed_prs[i : i + MAX_BATCH_SIZE]

        except Exception as e:
            logger.warning(
                f"Failed to process repository {repo.get('full_name', 'unknown')}: {str(e)}"
            )
            continue


@ocean.on_resync("Issue")
async def resync_issues(
    kind: str,
) -> t.AsyncGenerator[list[dict[str, t.Any]], None]:
    logger.info(f"Starting issue resync for kind: {kind}")

    handler = GithubClient.from_env()

    try:
        repositories = await handler.get_repositories()
    except Exception as e:
        logger.error(f"Failed to fetch repositories: {str(e)}")
        return

    logger.info(f"Retrieved {len(repositories)} repositories for issue sync")

    for repo in repositories:
        try:
            owner, repo_name = repo["full_name"].split("/")
            logger.info(f"Fetching issues for repository: {repo_name}")
            issues = await handler.get_issues(owner, repo_name)
            logger.info(f"Retrieved {len(issues)} issues for {repo_name}")

            # Process issues in batches
            processed_issues = [
                {
                    "id": str(issue["id"]),
                    "number": issue["number"],
                    "title": issue["title"],
                    "state": issue["state"],
                    "url": issue["html_url"],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "repository": repo["full_name"],
                    "author": issue["user"]["login"],
                    "labels": [label["name"] for label in issue["labels"]],
                    "assignees": [assignee["login"] for assignee in issue["assignees"]],
                }
                for issue in issues
            ]

            # Yield issues in batches
            for i in range(0, len(processed_issues), MAX_BATCH_SIZE):
                yield processed_issues[i : i + MAX_BATCH_SIZE]

        except Exception as e:
            logger.warning(
                f"Failed to process repository {repo.get('full_name', 'unknown')}: {str(e)}"
            )
            continue


@ocean.on_resync("Team")
async def resync_teams(
    kind: str,
) -> t.AsyncGenerator[list[dict[str, t.Any]], None]:
    logger.info(f"Starting team resync for kind: {kind}")

    handler = GithubClient.from_env()
    org = os.getenv("GITHUB_ORG")
    if not org:
        logger.warning("GITHUB_ORG is not set, returning empty list")
        return

    try:
        logger.info(f"Fetching teams for organization: {org}")
        teams = await handler.get_teams(org)
    except Exception as e:
        logger.error(f"Failed to fetch teams: {str(e)}")
        return

    logger.info(f"Retrieved {len(teams)} teams")

    result = [
        {
            "id": str(team["id"]),
            "name": team["name"],
            "slug": team["slug"],
            "description": team["description"],
            "privacy": team["privacy"],
            "url": team["html_url"],
        }
        for team in teams
    ]
    logger.info(f"Processed {len(result)} teams")

    # Yield teams in batches
    for i in range(0, len(result), MAX_BATCH_SIZE):
        yield result[i : i + MAX_BATCH_SIZE]


@ocean.on_resync("Workflow")
async def resync_workflows(
    kind: str,
) -> t.AsyncGenerator[list[dict[str, t.Any]], None]:
    logger.info(f"Starting workflow resync for kind: {kind}")

    handler = GithubClient.from_env()

    try:
        repositories = await handler.get_repositories()
    except Exception as e:
        logger.error(f"Failed to fetch repositories: {str(e)}")
        return

    logger.info(f"Retrieved {len(repositories)} repositories for workflow sync")
    all_workflows = []

    for repo in repositories:
        try:
            owner, repo_name = repo["full_name"].split("/")
            logger.info(f"Fetching workflows for repository: {repo_name}")
            workflows = await handler.get_workflows(owner, repo_name)
            logger.info(f"Retrieved {len(workflows)} workflows for {repo_name}")

            all_workflows.extend(
                [
                    {
                        "id": str(workflow["id"]),
                        "name": workflow["name"],
                        "path": workflow["path"],
                        "state": workflow["state"],
                        "url": workflow["html_url"],
                        "created_at": workflow["created_at"],
                        "updated_at": workflow["updated_at"],
                        "repository": repo["full_name"],
                    }
                    for workflow in workflows
                ]
            )
        except Exception as e:
            logger.warning(
                f"Failed to process repository {repo.get('full_name', 'unknown')}: {str(e)}"
            )
            continue

    logger.info(f"Processed total of {len(all_workflows)} workflows")

    # Yield workflows in batches
    for i in range(0, len(all_workflows), MAX_BATCH_SIZE):
        yield all_workflows[i : i + MAX_BATCH_SIZE]


@ocean.router.post("/webhook")
async def github_webhook(request: Request) -> tuple[dict[str, t.Any], int]:
    webhook_handler = WebhookHandler.from_env()
    return await webhook_handler.handle_webhook(request)
