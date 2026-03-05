from typing import Any, AsyncGenerator, Optional

import httpx
import re
from loguru import logger
from port_ocean.utils import http_async_client
from urllib.parse import parse_qs, urlparse

from .github_endpoints import GithubEndpoints


HTTP_STATUS_NOT_FOUND = 404


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

    async def get_new_usage_metrics_for_organization(
        self, organization: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """Fetches the manifest, downloads the signed URLs, and normalizes the data."""
        url = self._resolve_route_params(
            GithubEndpoints.COPILOT_ORGANIZATION_METRICS_28_DAY.value,
            {"org": organization["login"]},
        )

        report_manifest = await self.send_api_request(
            "get",
            url,
            ignore_status_code=[self.forbidden_status_code, HTTP_STATUS_NOT_FOUND],
        )

        if not report_manifest:
            logger.info(
                f'No usage metrics found for organization {organization["login"]}'
            )
            return None

        if isinstance(report_manifest, list):
            report_manifest = report_manifest[0] if report_manifest else {}

        download_links: list[str] = report_manifest.get("download_links", [])
        results: list[dict[str, Any]] = []

        for signed_url in download_links:
            report_data = await self._fetch_report_from_signed_url(signed_url)
            if report_data:
                if not isinstance(report_data, list):
                    logger.warning(
                        f"Expected report data to be a list but got {type(report_data)}. Wrapping it in a list for normalization."
                    )
                    report_data = [report_data]

                normalized_data = [
                    self._normalize_usage_record(record) for record in report_data
                ]
                results.extend(normalized_data)

        return results or None

    async def _fetch_report_from_signed_url(
        self, signed_url: str
    ) -> list[dict[str, Any]] | None:
        logger.debug("Fetching report from signed URL")
        try:
            response = await self._client.request(method="get", url=signed_url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching report from signed URL: {e}")
            return None

    def _normalize_usage_record(self, report_record: dict[str, Any]) -> dict[str, Any]:
        """
        Reshapes the new Usage Metrics flat schema into the deeply nested Legacy schema so the existing YAML JQ mapping just works
        """
        return {
            "date": report_record.get("day", ""),
            "total_active_users": report_record.get("daily_active_users", 0)
            or report_record.get("total_active_users", 0),
            "copilot_ide_code_completions": {
                "editors": [
                    {
                        "models": [
                            {
                                "languages": [
                                    {
                                        "total_code_suggestions": report_record.get(
                                            "code_generation_activity_count", 0
                                        ),
                                        "total_code_acceptances": report_record.get(
                                            "code_acceptance_activity_count", 0
                                        ),
                                        "total_code_lines_suggested": report_record.get(
                                            "loc_suggested_to_add_sum", 0
                                        ),
                                        "total_code_lines_accepted": report_record.get(
                                            "loc_added_sum", 0
                                        ),
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            "copilot_ide_chat": {
                "editors": [
                    {
                        "total_engaged_users": report_record.get(
                            "monthly_active_chat_users", 0
                        ),
                        "models": [
                            {
                                "total_chat_copy_events": 0,  # Fallbacks for dropped granular metrics
                                "total_chat_insertion_events": 0,
                                "total_chats": report_record.get(
                                    "user_initiated_interaction_count", 0
                                ),
                            }
                        ],
                    }
                ]
            },
        }

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
                logger.info(
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
