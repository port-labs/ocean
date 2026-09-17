"""Fetch options built from resource selectors and incremental cursor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from azure_devops.incremental import (
    ADVANCED_SECURITY_INCREMENTAL,
    RELEASE_DEPLOYMENT_INCREMENTAL,
    RELEASE_INCREMENTAL,
    flatten_advanced_security_params,
)
from integration import (
    AzureDevopsAdvancedSecuritySelector,
    AzureDevopsBuildSelector,
    AzureDevopsReleaseDeploymentSelector,
    AzureDevopsReleaseSelector,
    AzureDevopsTestRunSelector,
    AzureDevopsWorkItemResourceConfig,
)
from azure_devops.helpers.incremental_selectors import resolve_effective_datetime


@dataclass(frozen=True)
class WorkItemFetchOptions:
    wiql: str | None
    expand: str
    changed_after: datetime | None
    wiql_time_precision: bool

    @classmethod
    def from_selector(
        cls,
        selector: AzureDevopsWorkItemResourceConfig.AzureDevopsSelector,
        cursor: datetime | None,
    ) -> WorkItemFetchOptions:
        effective_changed_after = resolve_effective_datetime(
            cursor, selector.updated_since_datetime
        )
        return cls(
            wiql=selector.wiql,
            expand=selector.expand,
            changed_after=effective_changed_after,
            wiql_time_precision=cursor is not None,
        )


@dataclass(frozen=True)
class BuildFetchOptions:
    enrich_with_first_commit: bool
    min_time: datetime | None

    @classmethod
    def from_selector(
        cls,
        selector: AzureDevopsBuildSelector,
        cursor: datetime | None,
    ) -> BuildFetchOptions:
        return cls(
            enrich_with_first_commit=selector.enrich_with_first_commit,
            min_time=resolve_effective_datetime(cursor, selector.updated_since_datetime),
        )


@dataclass(frozen=True)
class ReleaseFetchOptions:
    additional_params: dict[str, str]

    @classmethod
    def from_selector(
        cls,
        selector: AzureDevopsReleaseSelector,
        cursor: datetime | None,
    ) -> ReleaseFetchOptions:
        params = dict(selector.to_params())
        if cursor is not None:
            params.pop("minCreatedTime", None)
            params = RELEASE_INCREMENTAL.merge_params(params, cursor)
        return cls(additional_params=params)


@dataclass(frozen=True)
class ReleaseDeploymentFetchOptions:
    additional_params: dict[str, Any]

    @classmethod
    def from_selector(
        cls,
        selector: AzureDevopsReleaseDeploymentSelector,
        cursor: datetime | None,
    ) -> ReleaseDeploymentFetchOptions:
        if cursor is not None:
            params = RELEASE_DEPLOYMENT_INCREMENTAL.build_params(cursor)
        else:
            params = selector.to_api_params()
        return cls(additional_params=params)


@dataclass(frozen=True)
class TestRunQueryOptions:
    include_results: bool
    coverage_config: Any
    min_last_updated_date: datetime | None
    max_last_updated_date: datetime | None

    @classmethod
    def from_selector(
        cls,
        selector: AzureDevopsTestRunSelector,
        cursor: datetime | None,
    ) -> TestRunQueryOptions:
        return cls(
            include_results=selector.include_results,
            coverage_config=selector.code_coverage,
            min_last_updated_date=resolve_effective_datetime(
                cursor, selector.updated_since_datetime
            ),
            max_last_updated_date=selector.updated_until_datetime,
        )


@dataclass(frozen=True)
class AdvancedSecurityFetchOptions:
    params: dict[str, Any]

    @classmethod
    def from_selector(
        cls,
        selector: AzureDevopsAdvancedSecuritySelector,
        cursor: datetime | None,
    ) -> AdvancedSecurityFetchOptions:
        base_params: dict[str, Any] = {}
        if selector.criteria:
            base_params = selector.criteria.as_params
        flattened = flatten_advanced_security_params(base_params)
        if cursor is not None:
            flattened.pop("criteria.modifiedSince", None)
            flattened = ADVANCED_SECURITY_INCREMENTAL.merge_params(flattened, cursor)
        return cls(params=flattened)
