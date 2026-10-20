from typing import Any, Literal, Optional, cast

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.pull_request_review_stats import compute_review_stats
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
        return normalize_pull_request_comment(
            response,
            repo_name=repo_name,
            pull_request_number=pr_number,
            comment_type=comment_type,
        )

    async def get_paginated_resources(
        self, options: ListPullRequestCommentOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        organization = options["organization"]
        repo_name = options["repo_name"]
        pr_number = options["pr_number"]
        repo_url = self._repo_url(organization, repo_name)

        list_endpoints: tuple[tuple[str, CommentType], ...] = (
            (f"{repo_url}/issues/{pr_number}/comments", "comment"),
            (f"{repo_url}/pulls/{pr_number}/comments", "review"),
            (f"{repo_url}/pulls/{pr_number}/reviews", "review-summary"),
        )
        for endpoint, comment_type in list_endpoints:
            async for batch in self.client.send_paginated_request(endpoint):
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

    async def fetch_all_comments(
        self, options: ListPullRequestCommentOptions
    ) -> list[dict[str, Any]]:
        """Collect every comment type for one pull request into a single list."""
        comments: list[dict[str, Any]] = []
        async for batch in self.get_paginated_resources(options):
            comments.extend(batch)
        return comments

    async def attach_comments_to_pull_requests(
        self,
        pull_requests: list[dict[str, Any]],
        *,
        organization: str,
    ) -> list[dict[str, Any]]:
        """Fetch all comments for every pull request and set ``__comments``.

        Parent selection is owned by the resource block's existing selector
        controls; this method does not apply any date gate.
        """
        enriched: list[dict[str, Any]] = []
        for pull_request in pull_requests:
            repo_name = cast(str, pull_request.get("__repository") or "")
            if not repo_name:
                logger.warning(
                    "Skipping comments fetch: pull request is missing __repository"
                )
                enriched.append(pull_request)
                continue

            comments = await self.fetch_all_comments(
                ListPullRequestCommentOptions(
                    organization=organization,
                    repo_name=repo_name,
                    pr_number=pull_request["number"],
                    pull_request_id=pull_request["id"],
                )
            )
            with_comments = dict(pull_request)
            with_comments["__comments"] = comments
            enriched.append(with_comments)
        return enriched

    async def fetch_timeline(
        self, organization: str, repo_name: str, pr_number: int
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        endpoint = (
            f"{self._repo_url(organization, repo_name)}/issues/{pr_number}/timeline"
        )
        async for batch in self.client.send_paginated_request(endpoint):
            events.extend(batch)
        return events

    async def enrich_pull_requests(
        self,
        pull_requests: list[dict[str, Any]],
        *,
        organization: str,
        include_comments: bool,
        include_review_stats: bool,
    ) -> list[dict[str, Any]]:
        """Attach ``__comments`` and/or ``__reviewStats`` for one resource block.

        The two flags are independent. Comments are fetched once when either is set.
        ``__comments`` is written only for ``include_comments``. ``__reviewStats`` is
        written only for ``include_review_stats``.
        """
        if not include_comments and not include_review_stats:
            return pull_requests

        enriched: list[dict[str, Any]] = []
        for pull_request in pull_requests:
            repo_name = cast(str, pull_request.get("__repository") or "")
            if not repo_name:
                logger.warning(
                    "Skipping comment enrichment: pull request is missing __repository"
                )
                enriched.append(pull_request)
                continue
            comments = await self.fetch_all_comments(
                ListPullRequestCommentOptions(
                    organization=organization,
                    repo_name=repo_name,
                    pr_number=pull_request["number"],
                    pull_request_id=pull_request["id"],
                )
            )
            updated = dict(pull_request)
            if include_comments:
                updated["__comments"] = comments
            if include_review_stats:
                timeline = await self.fetch_timeline(
                    organization, repo_name, pull_request["number"]
                )
                updated["__reviewStats"] = compute_review_stats(
                    comments, pull_request, timeline
                )
            enriched.append(updated)
        return enriched
