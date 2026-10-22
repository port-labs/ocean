from datetime import UTC, datetime
from typing import Any, AsyncIterator, Callable, Literal, Optional, cast

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.options import (
    ListPullRequestCommentOptions,
    SinglePullRequestCommentOptions,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

CommentType = Literal["comment", "review", "review-summary"]

_COMMENT_ENDPOINTS: dict[CommentType, str] = {
    # GET .../issues/comments/{id} (not nested under the issue/PR number)
    "comment": "issues/comments/{comment_id}",
    "review": "pulls/comments/{comment_id}",
    "review-summary": "pulls/{pr_number}/reviews/{comment_id}",
}


def filter_prs_by_date(
    prs: list[dict[str, Any]], date_field: str, cutoff: datetime
) -> list[dict[str, Any]]:

    return [
        pr
        for pr in prs
        if (
            (value := pr.get(date_field))
            and datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            >= cutoff
        )
    ]


async def paginate_closed_pull_requests(
    pages: AsyncIterator[list[dict[str, Any]]],
    *,
    enrich: Callable[[dict[str, Any]], dict[str, Any]],
    max_results: Optional[int],
    cutoff: Optional[datetime],
    include_field: str,
    stop_field: str,
    log_prefix: str,
    repo_name: str,
    organization: str,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Paginate closed pull requests for both the REST and GraphQL exporters.

    Each page is filtered by ``include_field`` against ``cutoff`` and capped to
    ``max_results`` (counting in-window PRs); pagination stops at the cutoff via
    ``stop_field``.
    """
    if cutoff is None:
        raise ValueError("paginate_closed_pull_requests requires a cutoff")

    total_count = 0
    async for page in pages:
        if not page:
            logger.info(
                f"{log_prefix} No more closed pull requests returned for repository "
                f"{repo_name} from {organization}; stopping."
            )
            break

        in_window = filter_prs_by_date(page, include_field, cutoff)
        if max_results is not None:
            remaining = max_results - total_count
            if remaining <= 0:
                break
            in_window = in_window[:remaining]

        batch = [enrich(pr) for pr in in_window]
        if batch:
            logger.info(
                f"{log_prefix} Fetched closed pull requests batch of {len(batch)} "
                f"from {repo_name} from {organization} "
                f"(total so far: {total_count + len(in_window)})"
            )
            yield batch
        total_count += len(in_window)

        # pages are sorted by stop_field desc and closed_at <= updated_at, so once the
        # last item predates the cutoff no later page can hold an in-window PR.
        if not filter_prs_by_date(page[-1:], stop_field, cutoff):
            logger.info(
                f"{log_prefix} Reached cutoff for closed pull requests of "
                f"{repo_name} from {organization}; stopping."
            )
            break

    logger.info(
        f"{log_prefix} Fetched total of {total_count} closed pull requests "
        f"from {organization}/{repo_name}"
    )


def normalize_pull_request_comment(
    raw: dict[str, Any],
    *,
    repo_name: str,
    pull_request_number: int,
    comment_type: CommentType,
) -> dict[str, Any]:
    """Keep raw GitHub comment fields and attach only derived identifiers.

    Conversation comments, inline review comments, and review bodies come from
    different GitHub APIs. Map from the raw fields (``body``, ``user.login``,
    ``created_at`` / ``submitted_at``, ``html_url``). ``__commentId`` includes
    the PR number and comment type because GitHub comment id spaces collide.
    """
    return {
        **raw,
        "__commentId": f"{repo_name}/{pull_request_number}/{comment_type}/{raw['id']}",
        "__commentType": comment_type,
    }


def _repo_url(client: GithubRestClient, organization: str, repo_name: str) -> str:
    return f"{client.base_url}/repos/{organization}/{repo_name}"


async def get_pull_request_comment(
    client: GithubRestClient, options: SinglePullRequestCommentOptions
) -> Optional[RAW_ITEM]:
    organization = options["organization"]
    repo_name = options["repo_name"]
    pr_number = options["pr_number"]
    comment_type = cast(CommentType, options["comment_type"])
    endpoint = _COMMENT_ENDPOINTS[comment_type].format(
        pr_number=pr_number, comment_id=options["comment_id"]
    )
    response = await client.send_api_request(
        f"{_repo_url(client, organization, repo_name)}/{endpoint}"
    )
    if not response:
        logger.warning(
            f"No pull request {comment_type} {options['comment_id']} found "
            f"for {organization}/{repo_name}#{pr_number}"
        )
        return None
    return normalize_pull_request_comment(
        response,
        repo_name=repo_name,
        pull_request_number=pr_number,
        comment_type=comment_type,
    )


async def iter_pull_request_comments(
    client: GithubRestClient, options: ListPullRequestCommentOptions
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    organization = options["organization"]
    repo_name = options["repo_name"]
    pr_number = options["pr_number"]
    repo_url = _repo_url(client, organization, repo_name)

    list_endpoints: tuple[tuple[str, CommentType], ...] = (
        (f"{repo_url}/issues/{pr_number}/comments", "comment"),
        (f"{repo_url}/pulls/{pr_number}/comments", "review"),
        (f"{repo_url}/pulls/{pr_number}/reviews", "review-summary"),
    )
    for endpoint, comment_type in list_endpoints:
        async for batch in client.send_paginated_request(endpoint):
            normalized = [
                normalize_pull_request_comment(
                    item,
                    repo_name=repo_name,
                    pull_request_number=pr_number,
                    comment_type=comment_type,
                )
                for item in batch
            ]
            if normalized:
                logger.info(
                    f"Fetched {len(normalized)} pull request {comment_type} "
                    f"items for {organization}/{repo_name}#{pr_number}"
                )
                yield normalized


async def fetch_all_pull_request_comments(
    client: GithubRestClient, options: ListPullRequestCommentOptions
) -> list[dict[str, Any]]:
    """Collect every comment type for one pull request into a single list."""
    comments: list[dict[str, Any]] = []
    async for batch in iter_pull_request_comments(client, options):
        comments.extend(batch)
    return comments


async def attach_pull_request_comments(
    client: GithubRestClient,
    pull_requests: list[dict[str, Any]],
    *,
    organization: str,
) -> list[dict[str, Any]]:
    """Fetch all comments for every pull request and set ``__comments``."""
    enriched: list[dict[str, Any]] = []
    for pull_request in pull_requests:
        repo_name = cast(str, pull_request.get("__repository") or "")
        if not repo_name:
            logger.warning(
                "Skipping comments fetch: pull request is missing __repository"
            )
            enriched.append(pull_request)
            continue

        comments = await fetch_all_pull_request_comments(
            client,
            ListPullRequestCommentOptions(
                organization=organization,
                repo_name=repo_name,
                pr_number=pull_request["number"],
                pull_request_id=pull_request["id"],
            ),
        )
        with_comments = dict(pull_request)
        with_comments["__comments"] = comments
        enriched.append(with_comments)
    return enriched


async def attach_comments_if_requested(
    client: GithubRestClient | None,
    pull_requests: list[dict[str, Any]],
    *,
    organization: str,
    include_comments: bool,
) -> list[dict[str, Any]]:
    if not include_comments or not pull_requests:
        return pull_requests
    if client is None:
        logger.warning("Skipping pull request comments; no REST client")
        return pull_requests
    return await attach_pull_request_comments(
        client, pull_requests, organization=organization
    )
