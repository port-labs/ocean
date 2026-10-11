from typing import Any

from google.api_core.exceptions import NotFound, PermissionDenied
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from gcp_core.clients import get_asset_client
from gcp_core.helpers.ratelimiter.fixed_window import FixedWindowLimiter
from gcp_core.search.paginated_query import paginated_query
from gcp_core.search.resource_searches import (
    search_all_folders,
    search_all_organizations,
)
from gcp_core.utils import (
    EXTRA_PROJECT_FIELD,
    AssetTypesWithSpecialHandling,
    parse_protobuf_messages,
)
from asyncio import BoundedSemaphore

# listAssets allows at most 1000 assets per page. searchAllIamPolicies allows 500.
_LIST_ASSETS_PAGE_SIZE = 1000
_IAM_POLICY_SEARCH_PAGE_SIZE = 500
_FOLDER_SCOPE_FIELD = "__folder"
_ORGANIZATION_SCOPE_FIELD = "__organization"

_LIST_ASSETS_PERMISSION = {
    "IAM_POLICY": "cloudasset.assets.listIamPolicy",
    "ORG_POLICY": "cloudasset.assets.listOrgPolicy",
    "ACCESS_POLICY": "cloudasset.assets.listAccessPolicy",
    "OS_INVENTORY": "cloudasset.assets.listOSInventories",
    "RELATIONSHIP": "cloudasset.assets.listResource",
}


def iam_policy_search_result_to_asset(
    result: dict[str, Any],
    scope: dict[str, Any],
    scope_field: str,
) -> dict[str, Any]:
    """Match a searchAllIamPolicies hit to the listAssets asset shape.

    listAssets stores the allow policy on ``iam_policy``. searchAllIamPolicies
    stores the matching bindings on ``policy``. Mappings can use ``iam_policy``
    for both.
    """
    folders = result.get("folders") or []
    asset: dict[str, Any] = {
        "name": result.get("resource") or "",
        "asset_type": result.get("asset_type") or result.get("assetType") or "",
        "iam_policy": (
            result.get("policy") if isinstance(result.get("policy"), dict) else {}
        ),
        scope_field: scope,
    }
    project = result.get("project")
    if isinstance(project, str) and project:
        asset["project"] = project
    if isinstance(folders, list) and folders:
        asset["folders"] = list(folders)
    organization = result.get("organization")
    if isinstance(organization, str) and organization:
        asset["organization"] = organization
    return asset


def _attach_scope(
    assets: list[dict[str, Any]],
    scope: dict[str, Any],
    scope_field: str,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for asset in assets:
        if isinstance(asset, dict):
            asset[scope_field] = scope
            enriched.append(asset)
    return enriched


async def fetch_cloud_asset_content_in_scope(
    scope: dict[str, Any],
    semaphore: BoundedSemaphore,
    asset_type: str,
    content_type: str,
    asset_query: str | None = None,
    rate_limiter: FixedWindowLimiter | None = None,
    scope_field: str = EXTRA_PROJECT_FIELD,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Read one non-RESOURCE content type inside a project, folder, or organization."""
    scope_name = scope["name"]
    use_iam_policy_query = content_type == "IAM_POLICY" and bool(asset_query)
    if use_iam_policy_query:
        method = "search_all_iam_policies"
        page_size = _IAM_POLICY_SEARCH_PAGE_SIZE
        permission = "cloudasset.assets.searchAllIamPolicies"
        request: dict[str, Any] = {
            "scope": scope_name,
            "asset_types": [asset_type],
            "query": asset_query,
        }

        def parse_response(response: Any) -> list[dict[str, Any]]:
            results = parse_protobuf_messages(response.results)
            return [
                iam_policy_search_result_to_asset(result, scope, scope_field)
                for result in results
                if isinstance(result, dict)
            ]

    else:
        method = "list_assets"
        page_size = _LIST_ASSETS_PAGE_SIZE
        permission = _LIST_ASSETS_PERMISSION.get(
            content_type, "cloudasset.assets.listResource"
        )
        request = {
            "parent": scope_name,
            "asset_types": [asset_type],
            "content_type": content_type,
        }

        def parse_response(response: Any) -> list[dict[str, Any]]:
            return _attach_scope(
                parse_protobuf_messages(response.assets), scope, scope_field
            )

    async with semaphore:
        logger.info(
            f"Reading Cloud Asset content type {content_type} for {asset_type} in {scope_name}"
        )
        try:
            async for assets in paginated_query(
                get_asset_client(),
                method,
                request,
                parse_response,
                rate_limiter,
                page_size=page_size,
            ):
                yield assets
        except PermissionDenied as error:
            logger.error(
                f"Service account doesn't have permission {permission} on {scope_name} "
                f"for {asset_type} content type {content_type}. Error: {str(error.message)}"
            )
        except NotFound as error:
            logger.info(
                f"Couldn't read {content_type} assets in {scope_name} because it was not found. "
                f"Error: {str(error)}"
            )
        except Exception:
            logger.exception(
                f"Unexpected error reading {content_type} assets for {asset_type} in {scope_name}"
            )
            raise
        else:
            logger.info(
                f"Finished reading {content_type} assets for {asset_type} in {scope_name}"
            )


async def iter_cloud_asset_content(
    asset_type: str,
    content_type: str,
    asset_query: str | None,
    rate_limiter: FixedWindowLimiter,
    semaphore: BoundedSemaphore,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Read a non-RESOURCE content type for one asset type.

    Project resources are listed once per accessible project. Folder and
    organization asset types are listed on those scopes, because their policies
    are not children of a project and an organization-wide list would also
    return every descendant project.
    """
    if asset_type == AssetTypesWithSpecialHandling.FOLDER:
        async for folders in search_all_folders():
            for folder in folders:
                async for batch in fetch_cloud_asset_content_in_scope(
                    folder,
                    semaphore,
                    asset_type,
                    content_type,
                    asset_query,
                    rate_limiter,
                    _FOLDER_SCOPE_FIELD,
                ):
                    yield batch
        return

    if asset_type == AssetTypesWithSpecialHandling.ORGANIZATION:
        async for organizations in search_all_organizations():
            for organization in organizations:
                async for batch in fetch_cloud_asset_content_in_scope(
                    organization,
                    semaphore,
                    asset_type,
                    content_type,
                    asset_query,
                    rate_limiter,
                    _ORGANIZATION_SCOPE_FIELD,
                ):
                    yield batch
        return

    from gcp_core.search.iterators import iterate_per_available_project

    async for batch in iterate_per_available_project(
        fetch_cloud_asset_content_in_scope,
        asset_type=asset_type,
        content_type=content_type,
        asset_query=asset_query,
        rate_limiter=rate_limiter,
        semaphore=semaphore,
    ):
        yield batch
