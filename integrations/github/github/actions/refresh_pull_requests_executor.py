from dataclasses import dataclass
from functools import partial
from typing import Literal, cast

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

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
from github.core.exporters.pull_request_exporter import fetch_single_pull_request
from github.core.exporters.pull_request_exporter.utils import (
    matches_pull_request_selector_states,
)
from github.clients.rate_limiter.utils import RateLimitInfo
from github.helpers.exceptions import InvalidActionParametersException
from github.helpers.utils import ObjectKind
from integration import GithubPortAppConfig, GithubPullRequestConfig

MAX_PULL_REQUESTS_TO_REFRESH = 50
MAX_CONCURRENT_PR_REFRESHES = 5


class PullRequestRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    org: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    prNumber: int = Field(ge=1)


class RefreshPullRequestsInputs(AbstractGithubActionInput):
    pullRequests: list[PullRequestRef] = Field(max_length=MAX_PULL_REQUESTS_TO_REFRESH)

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


KNOWN_PULL_REQUEST_STATES = {"open", "closed", "merged"}


@dataclass(frozen=True, slots=True)
class _RefreshOutcome:
    ref: str
    status: Literal["refreshed", "skipped", "failed", "unknown"]
    detail: str
    url: str | None = None
    raw: RAW_ITEM | None = None


def _pull_request_configs(
    port_app_config: GithubPortAppConfig,
) -> list[GithubPullRequestConfig]:
    configs = [
        resource
        for resource in port_app_config.resources
        if resource.kind == ObjectKind.PULL_REQUEST
    ]
    if not configs:
        raise RefreshPullRequestsError(
            "No pull-request resource is configured in the integration mapping"
        )
    return configs


def _format_outcome(outcome: _RefreshOutcome) -> str:
    extra = outcome.url or outcome.detail
    return f"{outcome.ref} ({extra})" if extra else outcome.ref


def _completion_message(outcomes: list[_RefreshOutcome]) -> str:
    refreshed = [outcome for outcome in outcomes if outcome.status == "refreshed"]
    skipped = [outcome for outcome in outcomes if outcome.status == "skipped"]
    failed = [outcome for outcome in outcomes if outcome.status == "failed"]
    unknown = [outcome for outcome in outcomes if outcome.status == "unknown"]
    parts = [
        (
            f"Refreshed {len(refreshed)}, skipped {len(skipped)}, "
            f"failed {len(failed)}, unknown {len(unknown)}."
        )
    ]
    if refreshed:
        parts.append("Refreshed: " + ", ".join(_format_outcome(o) for o in refreshed))
    if skipped:
        parts.append("Skipped: " + ", ".join(_format_outcome(o) for o in skipped))
    if failed:
        parts.append("Failed: " + ", ".join(_format_outcome(o) for o in failed))
    if unknown:
        parts.append("Unknown: " + ", ".join(_format_outcome(o) for o in unknown))
    return " ".join(parts)


class RefreshPullRequestsExecutor(AbstractGithubExecutor):
    ACTION_NAME = "refresh_pull_requests"

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

    async def _rate_limit_infos(self, run: IntegrationRun) -> list[RateLimitInfo]:
        infos = []
        for organization in self._orgs_for_rate_limit(run):
            client = await create_github_client_for_org(organization)
            info = client.get_rate_limit_status()
            if info:
                infos.append(info)
        return infos

    @staticmethod
    def _is_info_close_to_rate_limit(info: RateLimitInfo) -> bool:
        # The pre-check backs off without sending requests, so an expired window
        # must not keep blocking the run on a stale `remaining`.
        return (
            not info.is_expired
            and info.remaining < MIN_REMAINING_RATE_LIMIT_FOR_ACTIONS
        )

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return any(
            self._is_info_close_to_rate_limit(info)
            for info in await self._rate_limit_infos(run)
        )

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return max(
            (
                info.seconds_until_reset
                for info in await self._rate_limit_infos(run)
                if self._is_info_close_to_rate_limit(info)
            ),
            default=0.0,
        )

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
        resource_configs = _pull_request_configs(port_app_config)

        await ocean.port_client.post_run_log(
            run,
            (
                f"Refreshing {len(pull_requests)} pull request(s) across "
                f"{len(resource_configs)} pull-request mapping(s)"
            ),
            status_label="Refreshing PRs",
            should_raise=False,
        )

        fetch_outcomes = await throttle_batch_operation(
            [
                partial(self._fetch_one, pull_request, resource_config)
                for resource_config in resource_configs
                for pull_request in pull_requests
            ],
            MAX_CONCURRENT_PR_REFRESHES,
        )
        outcomes = await self._register_fetched(list(fetch_outcomes))

        failed = sum(1 for outcome in outcomes if outcome.status == "failed")
        message = _completion_message(outcomes)
        await ocean.port_client.post_run_log(run, message, should_raise=False)
        await ocean.port_client.report_run_completed(
            run,
            success=failed == 0,
            message=message,
            status_label="PRs refreshed" if failed == 0 else "Refresh failed",
        )

    async def _register_fetched(
        self,
        fetch_outcomes: list[_RefreshOutcome],
    ) -> list[_RefreshOutcome]:
        outcomes: list[_RefreshOutcome] = [
            outcome for outcome in fetch_outcomes if outcome.status != "refreshed"
        ]
        fetched = [
            outcome
            for outcome in fetch_outcomes
            if outcome.status == "refreshed" and outcome.raw is not None
        ]
        if not fetched:
            return outcomes

        raws = [outcome.raw for outcome in fetched if outcome.raw is not None]
        try:
            await ocean.register_raw(ObjectKind.PULL_REQUEST, raws)
        except Exception as error:
            logger.exception("Failed to upsert pull requests into the catalog")
            outcomes.extend(
                _RefreshOutcome(
                    ref=outcome.ref,
                    status="failed",
                    detail=f"catalog upsert failed: {error}",
                    url=outcome.url,
                )
                for outcome in fetched
            )
            return outcomes

        outcomes.extend(fetched)
        return outcomes

    async def _fetch_one(
        self,
        pull_request: PullRequestRef,
        resource_config: GithubPullRequestConfig,
    ) -> _RefreshOutcome:
        ref = (
            f"{pull_request.org}/{pull_request.repo}#{pull_request.prNumber} "
            f"({resource_config.selector.api})"
        )
        try:
            raw = await fetch_single_pull_request(
                organization=pull_request.org,
                repo_name=pull_request.repo,
                pr_number=pull_request.prNumber,
                resource_config=resource_config,
            )
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
        if state and state not in KNOWN_PULL_REQUEST_STATES:
            return _RefreshOutcome(
                ref=ref,
                status="unknown",
                detail=f"unrecognized state '{state}'",
            )
        allowed_states = {item.lower() for item in resource_config.selector.states}
        if not matches_pull_request_selector_states(state, allowed_states):
            return _RefreshOutcome(
                ref=ref,
                status="skipped",
                detail=(
                    f"state '{state}' is not in selector states "
                    f"{sorted(allowed_states)}"
                ),
            )

        url = str(
            raw.get("html_url")
            or raw.get("url")
            or (
                f"https://github.com/{pull_request.org}/{pull_request.repo}"
                f"/pull/{pull_request.prNumber}"
            )
        )
        return _RefreshOutcome(
            ref=ref,
            status="refreshed",
            detail="ok",
            url=url,
            raw=raw,
        )
