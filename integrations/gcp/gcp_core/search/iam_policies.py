"""Explicit IAM allow policies via Cloud Asset Inventory searchAllIamPolicies.

This is the only registered Cloud Asset API. ``policyQuery`` is the
searchAllIamPolicies query and is not sent to any other GCP API.
"""

from asyncio import BoundedSemaphore
from typing import Any, Literal

from google.api_core.exceptions import NotFound, PermissionDenied
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig, Selector
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from pydantic.v1 import Field, validator

from gcp_core.clients import get_asset_client
from gcp_core.search.cloud_asset_registry import CloudAssetApi, register
from gcp_core.search.paginated_query import paginated_query

IAM_POLICY_KIND = "iam.googleapis.com/Policy"
_SEARCH_PAGE_SIZE = 500
_BINDING_BATCH_SIZE = 100


class IamPolicySelector(Selector):
    asset_types: list[str] = Field(
        alias="assetTypes",
        min_items=1,
        title="Asset Types",
        description=(
            "Asset types whose explicit IAM allow policies are read with searchAllIamPolicies. "
            "At least one type is required so a resync does not inventory every policy in every accessible project. "
            "Policies are read once per accessible project, the same scope as other GCP resource kinds. "
            "Example: cloudresourcemanager.googleapis.com/Project"
        ),
    )
    policy_query: str | None = Field(
        default=None,
        alias="policyQuery",
        title="Server-side IAM policy query",
        description=(
            "Optional query sent only to Cloud Asset Inventory searchAllIamPolicies. "
            "This is not the JQ selector query, and it is not sent to searchAllResources or any other Cloud Asset API. "
            "The query is compared to each explicit allow-policy binding (principal, role, and condition). "
            "Only matching bindings are returned. Example: memberTypes:serviceAccount. "
            "See <a target='_blank' href='https://cloud.google.com/asset-inventory/docs/searching-iam-policies'>IAM policy search syntax</a>."
        ),
    )

    @validator("asset_types")
    def _strip_asset_types(cls, value: list[str]) -> list[str]:
        cleaned = [asset_type.strip() for asset_type in value]
        if any(not asset_type for asset_type in cleaned):
            raise ValueError("assetTypes entries must be non-empty strings")
        return cleaned

    @validator("policy_query", pre=True)
    def _blank_policy_query_is_unset(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("policyQuery must be a string")
        stripped = value.strip()
        return stripped or None


class IamPolicyResourceConfig(ResourceConfig):
    kind: Literal["iam.googleapis.com/Policy"] = Field(
        title="GCP IAM Allow Policy",
        description=(
            "Explicit IAM allow-policy bindings from Cloud Asset Inventory searchAllIamPolicies. "
            "Each item is one binding member (resource, role, and member), not effective or inherited access."
        ),
    )
    selector: IamPolicySelector = Field(
        title="IAM Policy Selector",
        description=(
            "Selector for explicit IAM allow policies. "
            "policyQuery is sent only to searchAllIamPolicies."
        ),
    )


def validate_iam_policy_raw(resource: dict[str, Any]) -> None:
    selector = resource.get("selector") or {}
    if not isinstance(selector, dict):
        raise ValueError(
            f"{IAM_POLICY_KIND} selector must be a mapping that includes assetTypes"
        )
    asset_types = selector.get("assetTypes", selector.get("asset_types"))
    if not isinstance(asset_types, list) or not asset_types:
        raise ValueError(
            f"{IAM_POLICY_KIND} requires selector.assetTypes with at least one "
            "asset type so a resync does not inventory every IAM allow policy"
        )
    if any(
        not isinstance(asset_type, str) or not asset_type.strip()
        for asset_type in asset_types
    ):
        raise ValueError(
            f"{IAM_POLICY_KIND} selector.assetTypes must be a list of non-empty strings"
        )


def _condition_or_none(binding: dict[str, Any]) -> dict[str, Any] | None:
    condition = binding.get("condition")
    if not isinstance(condition, dict):
        return None
    if not any(
        condition.get(key) for key in ("expression", "title", "description", "location")
    ):
        return None
    return {
        "expression": condition.get("expression") or "",
        "title": condition.get("title") or "",
        "description": condition.get("description") or "",
        "location": condition.get("location") or "",
    }


def _split_member(member: str) -> tuple[str, str]:
    if ":" not in member:
        return member, ""
    member_type, member_id = member.split(":", 1)
    return member_type, member_id


def expand_iam_policy_bindings(
    policies: list[dict[str, Any]],
    project: dict[str, Any],
) -> list[dict[str, Any]]:
    """Turn searchAllIamPolicies results into one item per binding member."""
    from gcp_core.utils import EXTRA_PROJECT_FIELD

    bindings: list[dict[str, Any]] = []
    for policy in policies:
        policy_body = policy.get("policy")
        if not isinstance(policy_body, dict):
            continue
        raw_bindings = policy_body.get("bindings") or []
        if not isinstance(raw_bindings, list):
            continue
        for binding in raw_bindings:
            if not isinstance(binding, dict):
                continue
            role = binding.get("role")
            if not isinstance(role, str) or not role:
                continue
            members = binding.get("members") or []
            if not isinstance(members, list):
                continue
            condition = _condition_or_none(binding)
            for member in members:
                if not isinstance(member, str) or not member:
                    continue
                member_type, member_id = _split_member(member)
                folders = policy.get("folders") or []
                bindings.append(
                    {
                        "resource": policy.get("resource") or "",
                        "asset_type": policy.get("asset_type")
                        or policy.get("assetType")
                        or "",
                        "project": policy.get("project") or "",
                        "folders": list(folders) if isinstance(folders, list) else [],
                        "organization": policy.get("organization") or "",
                        "role": role,
                        "member": member,
                        "member_type": member_type,
                        "member_id": member_id,
                        "condition": (
                            dict(condition) if condition is not None else None
                        ),
                        EXTRA_PROJECT_FIELD: project,
                    }
                )
    return bindings


def _batched(items: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    return [
        items[start : start + _BINDING_BATCH_SIZE]
        for start in range(0, len(items), _BINDING_BATCH_SIZE)
    ]


async def _search_project(
    project: dict[str, Any],
    semaphore: BoundedSemaphore,
    asset_types: list[str],
    policy_query: str | None = None,
    rate_limiter: Any = None,
    asset_type: str | None = None,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    del asset_type
    project_name = project["name"]
    request: dict[str, Any] = {
        "scope": project_name,
        "asset_types": list(asset_types),
    }
    if policy_query:
        request["query"] = policy_query

    def parse_response(response: Any) -> list[dict[str, Any]]:
        from gcp_core.utils import parse_protobuf_messages

        return parse_protobuf_messages(response.results)

    async with semaphore:
        logger.info(
            f"Searching explicit IAM allow policies in {project_name} "
            f"for asset types {asset_types}"
        )
        try:
            async for policies in paginated_query(
                get_asset_client(),
                "search_all_iam_policies",
                request,
                parse_response,
                rate_limiter,
                page_size=_SEARCH_PAGE_SIZE,
            ):
                expanded = expand_iam_policy_bindings(policies, project)
                for batch in _batched(expanded):
                    yield batch
        except PermissionDenied as error:
            logger.error(
                "Service account doesn't have permission "
                f"cloudasset.assets.searchAllIamPolicies on {project_name} "
                f"for asset types {asset_types}. Error: {str(error.message)}"
            )
        except NotFound as error:
            logger.info(
                f"Couldn't search IAM policies in {project_name} because it was not found. "
                f"Error: {str(error)}"
            )
        except Exception:
            logger.exception(
                f"Unexpected error searching IAM allow policies in {project_name}"
            )
            raise
        else:
            logger.info(f"Finished searching IAM allow policies in {project_name}")


async def _rate_limit() -> tuple[Any, BoundedSemaphore]:
    from gcp_core.helpers.ratelimiter.overrides import (
        SearchAllIamPoliciesQpmPerProject,
    )
    from gcp_core.utils import get_service_account_project_id

    limiter = SearchAllIamPoliciesQpmPerProject()
    try:
        project_id = get_service_account_project_id()
        return await limiter.limiter(project_id), await limiter.semaphore(project_id)
    except Exception as error:
        logger.warning(
            "Failed to compute the searchAllIamPolicies quota. "
            f"Using the default. Error: {str(error)}"
        )
        return await limiter.default_rate_limiter(), await limiter.default_semaphore()


async def fetch_iam_policies(config: ResourceConfig) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = config.selector
    asset_types = list(getattr(selector, "asset_types", None) or [])
    if not asset_types:
        raise ValueError(
            f"{IAM_POLICY_KIND} requires selector.assetTypes with at least one asset type"
        )
    policy_query = getattr(selector, "policy_query", None)
    if not isinstance(policy_query, str) or not policy_query:
        policy_query = None
    rate_limiter, semaphore = await _rate_limit()

    from gcp_core.search.iterators import iterate_per_available_project

    async for batch in iterate_per_available_project(
        _search_project,
        asset_types=asset_types,
        policy_query=policy_query,
        rate_limiter=rate_limiter,
        semaphore=semaphore,
        asset_type=IAM_POLICY_KIND,
    ):
        yield batch


register(
    CloudAssetApi(
        kind=IAM_POLICY_KIND,
        config_cls=IamPolicyResourceConfig,
        fetch=fetch_iam_policies,
        validate_raw=validate_iam_policy_raw,
    )
)
