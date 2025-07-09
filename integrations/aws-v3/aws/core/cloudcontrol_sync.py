import asyncio
import json
import typing
from typing import Any, List, Callable
from loguru import logger
from aiobotocore.session import AioSession
from aiobotocore.config import AioConfig
from aws.auth import AccountContext, get_all_account_sessions
from aws.auth import RegionResolver
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
import functools

from aws.core.helpers.utils import (
    CloudControlThrottlingConfig,
    CustomProperties,
    CloudControlClientProtocol,
    is_access_denied_exception,
    is_resource_not_found_exception,
    is_global_resource,
    fix_unserializable_date_properties,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from aws.core.paginator import AsyncPaginator


async def get_allowed_regions(session: AioSession, selector: Any) -> list[str]:
    resolver = RegionResolver(session, selector)
    return list(await resolver.get_allowed_regions())


async def describe_single_resource_cloudcontrol(
    kind: str,
    identifier: str,
    client: CloudControlClientProtocol,
) -> dict[str, str]:
    response = await client.get_resource(TypeName=kind, Identifier=identifier)
    resource_description = response["ResourceDescription"]
    serialized = resource_description.copy()
    serialized.update(
        {"Properties": json.loads(resource_description.get("Properties"))}
    )
    return serialized


async def process_single_cloudcontrol_resource(
    kind: str,
    identifier: str,
    cloudcontrol_client: Any,
    account_id: str,
    region: str,
) -> dict[str, Any]:
    try:
        response = await describe_single_resource_cloudcontrol(
            kind, identifier, client=cloudcontrol_client
        )
        response |= {
            CustomProperties.KIND.value: kind,
            CustomProperties.ACCOUNT_ID.value: account_id,
            CustomProperties.REGION.value: region,
        }
        return fix_unserializable_date_properties(response)
    except Exception as e:
        logger.error(f"Error processing resource {identifier}: {str(e)}")
        raise


async def process_resources_chunk(
    chunk: List[Any],
    kind: str,
    account_id: str,
    region: str,
    cloudcontrol_client: Any,
    identifier_extractor: Callable[[Any], str] = lambda x: (
        x.get("Identifier", "") if isinstance(x, dict) else x
    ),
) -> List[dict[str, Any]]:
    tasks = [
        process_single_cloudcontrol_resource(
            kind, identifier_extractor(item), cloudcontrol_client, account_id, region
        )
        for item in chunk
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    processed_resources = []
    for res in results:
        if isinstance(res, Exception):
            if is_resource_not_found_exception(res):
                continue
            else:
                raise res
        else:
            processed_resources.append(typing.cast(dict[str, Any], res))
    return processed_resources


async def resync_cloudcontrol(
    kind: str,
    session: AioSession,
    region: str,
    resource_config: Any,
    account_id: str,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = getattr(resource_config, "selector", None)
    use_get_resource_api = getattr(selector, "use_get_resource_api", False)
    logger.info(f"Resyncing {kind} in account {account_id} in region {region}")
    async with session.create_client(
        "cloudcontrol",
        region_name=region,
    ) as cloudcontrol_client:
        paginator = AsyncPaginator(
            client=cloudcontrol_client,
            method_name="list_resources",
            list_param="ResourceDescriptions",
        )
        try:
            async for resources_batch in paginator.paginate(TypeName=kind):
                if not resources_batch:
                    continue
                if use_get_resource_api:
                    async with session.create_client(
                        "cloudcontrol",
                        region_name=region,
                        config=AioConfig(
                            retries={
                                "max_attempts": CloudControlThrottlingConfig.MAX_RETRY_ATTEMPTS.value,
                                "mode": CloudControlThrottlingConfig.RETRY_MODE.value,
                            },
                        ),
                    ) as cloudcontrol_get_resource_client:
                        total_resources = len(resources_batch)
                        processed_count = 0
                        for chunk in process_list_in_chunks(resources_batch, 10):
                            processed_chunk = await process_resources_chunk(
                                chunk,
                                kind,
                                account_id,
                                region,
                                cloudcontrol_get_resource_client,
                            )
                            processed_count += len(chunk)
                            logger.info(
                                f"Processed {processed_count}/{total_resources} {kind} resources in batch from region {region} in account {account_id}"
                            )
                            yield processed_chunk
                else:
                    page_resources = []
                    for instance in resources_batch:
                        serialized = {
                            "Identifier": instance.get("Identifier"),
                            "Properties": json.loads(instance.get("Properties")),
                        }
                        serialized.update(
                            {
                                CustomProperties.KIND.value: kind,
                                CustomProperties.ACCOUNT_ID.value: account_id,
                                CustomProperties.REGION.value: region,
                            }
                        )
                        page_resources.append(
                            fix_unserializable_date_properties(serialized)
                        )
                    logger.info(
                        f"Processed batch of {len(page_resources)} {kind} resources from region {region} in account {account_id}"
                    )
                    yield page_resources
        except Exception as e:
            if is_access_denied_exception(e):
                logger.warning(
                    f"Skipping resyncing {kind} in region {region} in account {account_id} due to missing access permissions"
                )
            else:
                logger.error(f"Error resyncing {kind} in region {region}: {e}")
            raise e


def process_list_in_chunks(_list: List[Any], batch_size: int) -> List[List[Any]]:
    return [_list[i : i + batch_size] for i in range(0, len(_list), batch_size)]


async def _handle_global_resource_resync(
    kind: str,
    aws_resource_config: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = aws_resource_config.selector
    logger.info(f"Starting global resource resync for {kind}")
    async for account_context in get_all_account_sessions():
        account_id = account_context["details"]["Id"]
        account_name = account_context["details"]["Name"]
        logger.info(
            f"Processing global resource {kind} for account {account_id} ({account_name})"
        )
        regions = await get_allowed_regions(account_context["session"], selector)
        logger.debug(f"Found {len(regions)} allowed regions for account {account_id}")
        processed_successfully = False
        for region in regions:
            try:
                async for batch in resync_cloudcontrol(
                    kind,
                    account_context["session"],
                    region,
                    aws_resource_config,
                    account_id,
                ):
                    yield batch
                logger.info(
                    f"Successfully processed global resource {kind} in region {region} for account {account_id}"
                )
                processed_successfully = True
                break
            except Exception as e:
                if is_access_denied_exception(e):
                    logger.info(
                        f"Access denied for global resource {kind} in region {region} for account {account_id}, trying next region"
                    )
                    continue
                logger.error(
                    f"Error processing global resource {kind} in region {region} for account {account_id}: {e}"
                )
                raise e
        if not processed_successfully:
            logger.warning(
                f"Failed to process global resource {kind} in any region for account {account_id}"
            )


async def sync_account_region_resources(
    kind: str,
    aws_resource_config: Any,
    account_context: AccountContext,
    region: str,
    errors: list[Exception],
    error_regions: list[str],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    try:
        async for batch in resync_cloudcontrol(
            kind,
            account_context["session"],
            region,
            aws_resource_config,
            account_context["details"]["Id"],
        ):
            yield batch
    except Exception as exc:
        if is_access_denied_exception(exc):
            logger.info(
                f"Skipping access denied error in region {region} for account {account_context['details']['Id']}"
            )
            return
        logger.error(
            f"Error in region {region} for account {account_context['details']['Id']}: {exc}"
        )
        errors.append(exc)
        error_regions.append(region)


async def resync_resources_for_account_with_session(
    account_context: AccountContext,
    kind: str,
    aws_resource_config: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:

    errors: list[Exception] = []
    error_regions: list[str] = []
    account_id: str = account_context["details"]["Id"]
    REGION_CONCURRENCY_LIMIT = 10
    if is_global_resource(kind):
        logger.info(f"Handling global resource {kind} for account {account_id}")
        async for batch in _handle_global_resource_resync(kind, aws_resource_config):
            yield batch
        return
    logger.info(
        f"Processing account {account_id} with {REGION_CONCURRENCY_LIMIT} concurrent regions"
    )
    region_semaphore = asyncio.Semaphore(REGION_CONCURRENCY_LIMIT)
    selector = aws_resource_config.selector
    regions = await get_allowed_regions(account_context["session"], selector)
    region_tasks = []
    for region in regions:
        region_tasks.append(
            semaphore_async_iterator(
                region_semaphore,
                functools.partial(
                    sync_account_region_resources,
                    kind,
                    aws_resource_config,
                    account_context,
                    region,
                    errors,
                    error_regions,
                ),
            )
        )
    async for batch in stream_async_iterators_tasks(*region_tasks):
        yield batch

    logger.info(f"Completed processing regions for account {account_id}")
    if errors:
        message = (
            f"Failed to fetch {kind} for these regions {error_regions} "
            f"with {len(errors)} errors in account {account_id}"
        )
        raise ExceptionGroup(message, errors)
