from typing import Any, Literal, Optional, cast

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import (
    ListPullRequestCommentOptions,
    SinglePullRequestCommentOptions,
)
from github.helpers.utils import enrich_with_organization, enrich_with_repository
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

CommentType = Literal["comment", "review", "review-summary"]

_COMMENT_ENDPOINTS: dict[CommentType, str] = {
    "comment": "issues/{pr_number}/comments/{comment_id}",
    "review": "pulls/comments/{comment_id}",
    "review-summary": "pulls/{pr_number}/reviews/{comment_id}",
}


def normalize_pull_request_comment(
    raw: dict[str, Any],
    *,
    organization: str,
    repo_name: str,
    pull_request_id: int,
    pull_request_number: int,
    comment_type: CommentType,
) -> dict[str, Any]:
    """Attach the fields the default comment mapping reads.

    Conversation comments, inline review comments, and review bodies come from
    different GitHub APIs. The normalized keys keep one blueprint shape.
    """
    author = (raw.get("user") or {}).get("login") or ""
    created_at = raw.get("created_at") or raw.get("submitted_at")
    comment_id = f"{repo_name}/{pull_request_number}/{comment_type}/{raw['id']}"
    enriched = enrich_with_organization(
        enrich_with_repository(dict(raw), repo_name), organization
    )
    enriched.update(
        {
            "__commentId": comment_id,
            "__body": raw.get("body") or "",
            "__author": author,
            "__createdAt": created_at,
            "__updatedAt": raw.get("updated_at") or created_at,
            "__url": raw.get("html_url") or "",
            "__commentType": comment_type,
            "__pullRequestId": pull_request_id,
            "__pullRequestNumber": pull_request_number,
        }
    )
    return enriched


class RestPullRequestCommentExporter(AbstractGithubExporter[GithubRestClient]):
    def _repo_url(self, organization: str, repo_name: str) -> str:
        return f"{self.client.base_url}/repos/{organization}/{repo_name}"

    async def get_resource(
        self, options: SinglePullRequestCommentOptions
    ) -> Optional[RAW_ITEM]:
        organization = options["organization"]
        repo_name = options["repo_name"]
        pr_number = options["pr_number"]
        comment_type = cast(CommentType, options["comment_type"])
        endpoint = _COMMENT_ENDPOINTS[comment_type].format(
            pr_number=pr_number, comment_id=options["comment_id"]
        )
        response = await self.client.send_api_request(
            f"{self._repo_url(organization, repo_name)}/{endpoint}"
        )
        if not response:
            logger.warning(
                f"No pull request {comment_type} {options['comment_id']} found "
                f"for {organization}/{repo_name}#{pr_number}"
            )
            return None
        if (
            comment_type == "review-summary"
            and not (response.get("body") or "").strip()
        ):
            return None
        return normalize_pull_request_comment(
            response,
            organization=organization,
            repo_name=repo_name,
            pull_request_id=options["pull_request_id"],
            pull_request_number=pr_number,
            comment_type=comment_type,
        )

    async def get_paginated_resources(
        self, options: ListPullRequestCommentOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        repo_name = options["repo_name"]
        pr_number = options["pr_number"]
        pull_request_id = options["pull_request_id"]
        repo_url = self._repo_url(organization, repo_name)

        list_endpoints: tuple[tuple[str, CommentType, bool], ...] = (
            (f"{repo_url}/issues/{pr_number}/comments", "comment", False),
            (f"{repo_url}/pulls/{pr_number}/comments", "review", False),
            (f"{repo_url}/pulls/{pr_number}/reviews", "review-summary", True),
        )
        for endpoint, comment_type, skip_empty_body in list_endpoints:
            async for batch in self.client.send_paginated_request(endpoint):
                normalized = [
                    normalize_pull_request_comment(
                        item,
                        organization=organization,
                        repo_name=repo_name,
                        pull_request_id=pull_request_id,
                        pull_request_number=pr_number,
                        comment_type=comment_type,
                    )
                    for item in batch
                    if not skip_empty_body or (item.get("body") or "").strip()
                ]
                if normalized:
                    logger.info(
                        f"Fetched {len(normalized)} pull request {comment_type} "
                        f"items for {organization}/{repo_name}#{pr_number}"
                    )
                    yield normalized
