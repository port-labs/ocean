import json
from dataclasses import dataclass
from functools import partial
from typing import Any, Literal, Optional, cast

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.core.ocean_types import RAW_ITEM
from port_ocean.utils.async_iterators import throttle_batch_operation

from github.actions.abstract_github_action_input import AbstractGithubActionInput
from github.actions.abstract_github_executor import (
    MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS,
    AbstractGithubExecutor,
)
from github.actions.exceptions import RefreshPullRequestsError
from github.actions.utils import extract_error_message
from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.pull_request_exporter import (
    GraphQLPullRequestExporter,
    RestPullRequestExporter,
)
from github.core.options import SinglePullRequestOptions
from github.helpers.exceptions import InvalidActionParametersException
from github.helpers.utils import GithubClientType, ObjectKind
from integration import GithubPortAppConfig, GithubPullRequestConfig

MAX_PULL_REQUESTS_TO_REFRESH = 100
MAX_CONCURRENT_PR_REFRESHES = 5


class PullRequestRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    org: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    prNumber: int = Field(ge=1)


class RefreshPullRequestsInputs(AbstractGithubActionInput):
    pullRequests: list[PullRequestRef]

    @field_validator("pullRequests", mode="before")
    @classmethod
    def parse_pull_requests(cls, value: Any) -> Any:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"pullRequests must be a JSON array: {error}"
                ) from error
        return value

    @model_validator(mode="after")
    def reject_oversized_batch(self) -> "RefreshPullRequestsInputs":
        if len(self.pullRequests) > MAX_PULL_REQUESTS_TO_REFRESH:
            raise ValueError(
                f"pullRequests cannot contain more than {MAX_PULL_REQUESTS_TO_REFRESH} "
                f"items (got {len(self.pullRequests)})"
            )
        return self

    def deduplicated(self) -> list[PullRequestRef]:
        seen: set[tuple[str, str, int]] = set()
        unique: list[PullRequestRef] = []
        for pull_request in self.pullRequests:
            key = (pull_request.org, pull_request.repo, pull_request.prNumber)
            if key in seen:
                continue
            seen.add(key)
            unique.append(pull_request)
        return unique


@dataclass(frozen=True, slots=True)
class _RefreshOutcome:
    ref: str
    status: Literal["refreshed", "skipped", "failed"]
    detail: str
    url: str | None = None


def _select_pull_request_config(
    port_app_config: GithubPortAppConfig,
) -> GithubPullRequestConfig:
    configs = [
        resource
        for resource in port_app_config.resources
        if resource.kind == ObjectKind.PULL_REQUEST
    ]
    if not configs:
        raise RefreshPullRequestsError(
            "No pull-request resource is configured in the integration mapping"
        )
    graphql_configs = [
        config for config in configs if config.selector.api == GithubClientType.GRAPHQL
    ]
    return graphql_configs[0] if graphql_configs else configs[0]


def _format_ref(pull_request: PullRequestRef) -> str:
    return f"{pull_request.org}/{pull_request.repo}#{pull_request.prNumber}"


def _raw_pr_url(raw: RAW_ITEM, pull_request: PullRequestRef) -> str:
    return str(
        raw.get("html_url")
        or raw.get("url")
        or (
            f"https://github.com/{pull_request.org}/{pull_request.repo}"
            f"/pull/{pull_request.prNumber}"
        )
    )


def _format_outcome(outcome: _RefreshOutcome) -> str:
    extra = outcome.url or outcome.detail
    return f"{outcome.ref} ({extra})" if extra else outcome.ref


def _completion_message(outcomes: list[_RefreshOutcome]) -> str:
    refreshed = [outcome for outcome in outcomes if outcome.status == "refreshed"]
    skipped = [outcome for outcome in outcomes if outcome.status == "skipped"]
    failed = [outcome for outcome in outcomes if outcome.status == "failed"]
    parts = [
        f"Refreshed {len(refreshed)}, skipped {len(skipped)}, failed {len(failed)}."
    ]
    if refreshed:
        parts.append("Refreshed: " + ", ".join(_format_outcome(o) for o in refreshed))
    if skipped:
        parts.append("Skipped: " + ", ".join(_format_outcome(o) for o in skipped))
    if failed:
        parts.append("Failed: " + ", ".join(_format_outcome(o) for o in failed))
    return " ".join(parts)


class RefreshPullRequestsExecutor(AbstractGithubExecutor):
    ACTION_NAME = "refresh_pull_requests"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return None

    def _orgs_for_rate_limit(self, run: IntegrationRun) -> list[str]:
        try:
            inputs = RefreshPullRequestsInputs.from_execution_properties(
                run.execution_properties
            )
        except InvalidActionParametersException:
            return []
        orgs: list[str] = []
        seen: set[str] = set()
        for pull_request in inputs.deduplicated():
            if pull_request.org in seen:
                continue
            seen.add(pull_request.org)
            orgs.append(pull_request.org)
        return orgs

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        orgs = self._orgs_for_rate_limit(run)
        if not orgs:
            return False
        client = await create_github_client_for_org(orgs[0])
        info = client.get_rate_limit_status()
        if not info:
            return False
        return info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        orgs = self._orgs_for_rate_limit(run)
        if not orgs:
            return 0.0
        client = await create_github_client_for_org(orgs[0])
        info = client.get_rate_limit_status()
        if not info:
            return 0.0
        return info.seconds_until_reset

    async def execute(self, run: IntegrationRun) -> None:
        inputs = RefreshPullRequestsInputs.from_execution_properties(
            run.execution_properties
        )
        pull_requests = inputs.deduplicated()
        if not pull_requests:
            await ocean.port_client.post_run_log(
                run, "nothing to refresh", should_raise=False
            )
            await ocean.port_client.report_run_completed(
                run,
                success=True,
                message="nothing to refresh",
                status_label="No refresh",
            )
            return

        port_app_config = cast(
            GithubPortAppConfig,
            await ocean.integration.port_app_config_handler.get_port_app_config(
                use_cache=False
            ),
        )
        resource_config = _select_pull_request_config(port_app_config)

        await ocean.port_client.post_run_log(
            run,
            f"Refreshing {len(pull_requests)} pull request(s)",
            status_label="Refreshing PRs",
            should_raise=False,
        )

        async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
            outcomes = await throttle_batch_operation(
                [
                    partial(self._refresh_one, pull_request, resource_config)
                    for pull_request in pull_requests
                ],
                MAX_CONCURRENT_PR_REFRESHES,
            )

        failed = sum(1 for outcome in outcomes if outcome.status == "failed")
        message = _completion_message(outcomes)
        await ocean.port_client.post_run_log(run, message, should_raise=False)
        await ocean.port_client.report_run_completed(
            run,
            success=failed == 0,
            message=message,
            status_label="PRs refreshed" if failed == 0 else "Refresh failed",
        )

    async def _refresh_one(
        self,
        pull_request: PullRequestRef,
        resource_config: GithubPullRequestConfig,
    ) -> _RefreshOutcome:
        ref = _format_ref(pull_request)
        try:
            raw = await self._fetch_pull_request(pull_request, resource_config)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return _RefreshOutcome(ref=ref, status="skipped", detail="not found")
            return _RefreshOutcome(
                ref=ref,
                status="failed",
                detail=extract_error_message(error.response),
            )
        except Exception as error:
            logger.exception(
                "Failed to refresh pull request {ref}",
                ref=ref,
            )
            return _RefreshOutcome(ref=ref, status="failed", detail=str(error))

        if not raw:
            return _RefreshOutcome(ref=ref, status="skipped", detail="not found")

        state = (raw.get("state") or "").lower()
        allowed_states = {item.lower() for item in resource_config.selector.states}
        if state and state not in allowed_states:
            return _RefreshOutcome(
                ref=ref,
                status="skipped",
                detail=(
                    f"state '{state}' is not in selector states "
                    f"{sorted(allowed_states)}"
                ),
            )

        url = _raw_pr_url(raw, pull_request)
        try:
            await ocean.register_raw(ObjectKind.PULL_REQUEST, [raw])
        except Exception as error:
            logger.exception(
                "Failed to upsert pull request {ref} into the catalog",
                ref=ref,
            )
            return _RefreshOutcome(
                ref=ref,
                status="failed",
                detail=f"catalog upsert failed: {error}",
                url=url,
            )

        logger.info("Refreshed pull request {ref}", ref=ref, html_url=url)
        return _RefreshOutcome(ref=ref, status="refreshed", detail="ok", url=url)

    async def _fetch_pull_request(
        self,
        pull_request: PullRequestRef,
        resource_config: GithubPullRequestConfig,
    ) -> Optional[RAW_ITEM]:
        is_graphql = resource_config.selector.api == GithubClientType.GRAPHQL
        exporter: AbstractGithubExporter[Any]
        if is_graphql:
            exporter = GraphQLPullRequestExporter(
                await create_github_client_for_org(
                    pull_request.org, GithubClientType.GRAPHQL
                )
            )
        else:
            exporter = RestPullRequestExporter(
                await create_github_client_for_org(pull_request.org)
            )

        return await exporter.get_resource(
            SinglePullRequestOptions(
                organization=pull_request.org,
                repo_name=pull_request.repo,
                pr_number=pull_request.prNumber,
                repo={"name": pull_request.repo} if is_graphql else None,
                enrich_with_first_commit=(
                    resource_config.selector.enrich_with_first_commit
                ),
                exclude_graphql_fields=resource_config.selector.exclude_graphql_fields,
            )
        )
