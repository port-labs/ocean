from typing import Any, AsyncGenerator, Optional

import httpx
import re
from loguru import logger
from port_ocean.utils import http_async_client
from urllib.parse import parse_qs, urlparse
import asyncio
from itertools import batched

from .github_endpoints import GithubEndpoints


class GitHubClient:
    def __init__(self, base_url: str, token: str):
        self._token = token
        self._client = http_async_client
        self._headers = self._get_headers()
        self.base_url = base_url
        self.NEXT_PATTERN = re.compile(r'<([^>]+)>; rel="next"')
        self.pagination_page_size_limit = 100
        self.pagination_header_name = "Link"
        self.copilot_disabled_status_code = 422
        self.forbidden_status_code = 403

    async def get_organizations(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for organizations in self._get_paginated_data(
            GithubEndpoints.LIST_ACCESSIBLE_ORGS.value
        ):
            yield organizations

    async def get_teams_of_organization(
        self, organization: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = self._resolve_route_params(
            GithubEndpoints.LIST_TEAMS.value, {"org": organization["login"]}
        )
        async for teams in self._get_paginated_data(
            url,
            ignore_status_code=[self.forbidden_status_code],
        ):
            yield teams

    async def get_legacy_metrics_for_organization(
        self, organization: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """Fetches the legacy inline-JSON metrics."""
        url = self._resolve_route_params(
            GithubEndpoints.COPILOT_ORGANIZATION_METRICS.value,
            {"org": organization["login"]},
        )
        return await self.send_api_request(
            "get",
            url,
            ignore_status_code=[
                self.copilot_disabled_status_code,
                self.forbidden_status_code,
            ],
        )

    async def get_organization_usage_metrics(
        self, organization: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        "Fetches the 28-day usage manifest and downloads metrics from signed URLs."
        logger.info(
            f"Fetching organization metrics download links for {organization['login']}"
        )
        url = self._resolve_route_params(
            GithubEndpoints.COPILOT_ORGANIZATION_METRICS_28_DAY.value,
            {"org": organization["login"]},
        )
        response = await self._send_api_request(
            "get",
            url,
            ignore_status_code=[self.forbidden_status_code],
        )

        if not response:
            logger.info(
                f"No usage metrics found for organization {organization['login']}"
            )
            return

        response_data = response.json()
        if not (download_links := response_data["download_links"]):
            logger.info(
                f"No usage metrics found for organization {organization['login']}"
            )
            return

        logger.info(
            f"Received {len(download_links)} report download links for organization {organization['login']} "
            f"covering {response_data['report_start_day']} to {response_data['report_end_day']}"
        )

        for signed_urls in batched(download_links, self.pagination_page_size_limit):
            reports = await asyncio.gather(
                *[
                    self._fetch_report_from_signed_url(signed_url)
                    for signed_url in signed_urls
                ]
            )
            yield [report for report in reports if report is not None]

    async def fetch_organization_usage_metrics(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for organizations_batch in self.get_organizations():
            for organization in organizations_batch:
                async for reports in self.get_organization_usage_metrics(organization):
                    day_totals = [
                        day
                        for report in reports
                        if report and "day_totals" in report
                        for day in report["day_totals"]
                    ]
                    if not day_totals:
                        continue

                    self._enrich_metrics_with_organization(
                        day_totals, organization, record_date_key="day"
                    )
                    yield day_totals

    async def _fetch_report_from_signed_url(
        self, signed_url: str
    ) -> dict[str, Any] | None:
        logger.debug("Fetching report from signed URL")
        try:
            response = await self._client.request(method="get", url=signed_url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching report from signed URL: {e}")
            return None

    async def get_metrics_for_team(
        self, organization: dict[str, Any], team: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        url = self._resolve_route_params(
            GithubEndpoints.COPILOT_TEAM_METRICS.value,
            {"org": organization["login"], "team": team["slug"]},
        )
        return await self.send_api_request(
            "get",
            url,
            ignore_status_code=[
                self.copilot_disabled_status_code,
                self.forbidden_status_code,
            ],
        )

    async def _get_paginated_data(
        self,
        url: str,
        ignore_status_code: Optional[list[int]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        while True:
            params = self._build_params(url)
            response = await self._send_api_request(
                method="get",
                path=url,
                params=params,
                ignore_status_code=ignore_status_code,
            )
            if not response:
                break
            json_data = response.json()
            yield json_data

            link_header = (
                response.headers.get(self.pagination_header_name, "")
                if response
                else ""
            )
            match = self.NEXT_PATTERN.search(link_header)
            if not match:
                break
            url = match.group(1).replace(self.base_url, "")

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        ignore_status_code: Optional[list[int]] = None,
    ) -> list[dict[str, Any]]:
        response = await self._send_api_request(
            method, path, params, data, ignore_status_code
        )
        return response.json() if response else []

    async def _send_api_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        ignore_status_code: Optional[list[int]] = None,
    ) -> httpx.Response | None:
        url = self._build_url(path)
        logger.debug(f"Sending {method} request to {url}")

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=self._headers,
                params=params,
                json=data,
            )
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(
                    f"Resource not found at {url} for the following params {params}"
                )
                return None

            if ignore_status_code and e.response.status_code in ignore_status_code:
                logger.warning(
                    f"Ignoring status code {e.response.status_code} for {method} request to {path}"
                )
                return None

            logger.error(f"HTTP status error for {method} request to {path}: {e}")
            raise

        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {method} request to {path}: {e}")
            raise

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _build_url(self, path: str) -> str:
        base_url = (
            self.base_url if not self.base_url.endswith("/") else self.base_url[:-1]
        )
        if path.startswith("/"):
            path = path[1:]
        return f"{base_url}/{path}"

    def _build_params(self, url: str) -> dict[str, Any]:
        base_params = {"per_page": self.pagination_page_size_limit}
        parsed_url = urlparse(url)
        if parsed_url.query:
            return {**parse_qs(parsed_url.query), **base_params}
        return base_params

    @staticmethod
    def _resolve_route_params(endpoint_template: str, params: dict[str, str]) -> str:
        """
        Replaces placeholders in the endpoint template with actual values from params.

        :param endpoint_template: The URL template containing placeholders like {organizationn}, {team}, etc.
        :param params: A dictionary mapping placeholder names to values.
        :return: A formatted string with placeholders replaced by their corresponding values.
        """
        return endpoint_template.format(**params)

    def _enrich_metrics_with_organization(
        self,
        metrics: list[dict[str, Any]],
        organization: dict[str, Any],
        record_date_key: str = "date",
    ) -> list[dict[str, Any]]:
        for metric in metrics:
            logger.info(
                f"Enriching metric of day {metric[record_date_key]} with organization {organization}"
            )
            metric["__organization"] = organization
        return metrics
