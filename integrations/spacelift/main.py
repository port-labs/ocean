"""Spacelift Ocean Integration main module."""

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from spacelift.client import create_spacelift_client
from spacelift.utils import ResourceKind, normalize_spacelift_resource, get_resource_url


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Spacelift integration."""
    logger.info("Starting Port Ocean Spacelift Integration")

    # Test client connection
    try:
        async with create_spacelift_client() as client:
            # Test authentication by making a simple query
            await client._authenticate()
            logger.info("Successfully connected to Spacelift API")
    except Exception as e:
        logger.error(f"Failed to connect to Spacelift API: {e}")
        raise e

    logger.info("Spacelift integration started successfully")


@ocean.on_resync(ResourceKind.SPACE)
async def on_resync_spaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Spacelift spaces.

    Args:
        kind: The resource kind being resynced

    Yields:
        Batches of space data
    """
    logger.info("Starting resync for Spacelift spaces")

    async with create_spacelift_client() as client:
        batch_count = 0
        async for spaces_batch in client.get_spaces():
            batch_count += 1
            logger.info(
                f"Received spaces batch {batch_count} with {len(spaces_batch)} spaces"
            )

            # Normalize the data and add URLs
            normalized_spaces = []
            account_name = ocean.integration_config.get("spacelift_account_name", "")

            for space in spaces_batch:
                normalized_space = normalize_spacelift_resource(
                    space, ResourceKind.SPACE
                )
                if account_name:
                    normalized_space["url"] = get_resource_url(
                        normalized_space, account_name
                    )
                normalized_spaces.append(normalized_space)

            yield normalized_spaces


@ocean.on_resync(ResourceKind.STACK)
async def on_resync_stacks(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Spacelift stacks.

    Args:
        kind: The resource kind being resynced

    Yields:
        Batches of stack data
    """
    logger.info("Starting resync for Spacelift stacks")

    async with create_spacelift_client() as client:
        batch_count = 0
        async for stacks_batch in client.get_stacks():
            batch_count += 1
            logger.info(
                f"Received stacks batch {batch_count} with {len(stacks_batch)} stacks"
            )

            # Normalize the data and add URLs
            normalized_stacks = []
            account_name = ocean.integration_config.get("spacelift_account_name", "")

            for stack in stacks_batch:
                normalized_stack = normalize_spacelift_resource(
                    stack, ResourceKind.STACK
                )
                if account_name:
                    normalized_stack["url"] = get_resource_url(
                        normalized_stack, account_name
                    )
                normalized_stacks.append(normalized_stack)

            yield normalized_stacks


@ocean.on_resync(ResourceKind.DEPLOYMENT)
async def on_resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Spacelift deployments (tracked runs).

    Args:
        kind: The resource kind being resynced

    Yields:
        Batches of deployment data
    """
    logger.info("Starting resync for Spacelift deployments (tracked runs)")

    async with create_spacelift_client() as client:
        batch_count = 0
        async for runs_batch in client.get_runs():
            # Filter for tracked runs only (deployments)
            tracked_runs = [run for run in runs_batch if run.get("type") == "TRACKED"]

            if tracked_runs:
                batch_count += 1
                logger.info(
                    f"Received deployments batch {batch_count} with {len(tracked_runs)} deployments"
                )

                # Normalize the data and add URLs
                normalized_deployments = []
                account_name = ocean.integration_config.get(
                    "spacelift_account_name", ""
                )

                for deployment in tracked_runs:
                    normalized_deployment = normalize_spacelift_resource(
                        deployment, ResourceKind.DEPLOYMENT
                    )
                    if account_name:
                        normalized_deployment["url"] = get_resource_url(
                            normalized_deployment, account_name
                        )
                    normalized_deployments.append(normalized_deployment)

                yield normalized_deployments


@ocean.on_resync(ResourceKind.POLICY)
async def on_resync_policies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Spacelift policies.

    Args:
        kind: The resource kind being resynced

    Yields:
        Batches of policy data
    """
    logger.info("Starting resync for Spacelift policies")

    async with create_spacelift_client() as client:
        batch_count = 0
        async for policies_batch in client.get_policies():
            batch_count += 1
            logger.info(
                f"Received policies batch {batch_count} with {len(policies_batch)} policies"
            )

            # Normalize the data and add URLs
            normalized_policies = []
            account_name = ocean.integration_config.get("spacelift_account_name", "")

            for policy in policies_batch:
                normalized_policy = normalize_spacelift_resource(
                    policy, ResourceKind.POLICY
                )
                if account_name:
                    normalized_policy["url"] = get_resource_url(
                        normalized_policy, account_name
                    )
                normalized_policies.append(normalized_policy)

            yield normalized_policies


@ocean.on_resync(ResourceKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Spacelift users.

    Args:
        kind: The resource kind being resynced

    Yields:
        Batches of user data
    """
    logger.info("Starting resync for Spacelift users")

    async with create_spacelift_client() as client:
        async for users_batch in client.get_users():
            logger.info(f"Received users batch with {len(users_batch)} users")

            # Normalize the data and add URLs
            normalized_users = []
            account_name = ocean.integration_config.get("spacelift_account_name", "")

            for user in users_batch:
                normalized_user = normalize_spacelift_resource(user, ResourceKind.USER)
                if account_name:
                    normalized_user["url"] = get_resource_url(
                        normalized_user, account_name
                    )
                normalized_users.append(normalized_user)

            yield normalized_users


@ocean.on_resync()
async def on_global_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Global resync handler for any Spacelift resource.

    This provides a fallback for any resource type not explicitly handled above.
    It enables customers to ingest any Spacelift resource out of the box.

    Args:
        kind: The resource kind being resynced

    Yields:
        Batches of resource data
    """
    logger.info(f"Global resync triggered for kind: {kind}")

    # Map kind to specific resource type if it matches our known types
    kind_mapping = {
        "spaces": ResourceKind.SPACE,
        "stacks": ResourceKind.STACK,
        "deployments": ResourceKind.DEPLOYMENT,
        "runs": ResourceKind.DEPLOYMENT,  # Allow "runs" as alias for deployments
        "policies": ResourceKind.POLICY,
        "users": ResourceKind.USER,
    }

    resource_type = kind_mapping.get(kind.lower())

    if resource_type:
        logger.info(f"Handling global resync for known resource type: {resource_type}")

        async with create_spacelift_client():
            # Route to appropriate handler
            if resource_type == ResourceKind.SPACE:
                async for batch in on_resync_spaces(kind):
                    yield batch
            elif resource_type == ResourceKind.STACK:
                async for batch in on_resync_stacks(kind):
                    yield batch
            elif resource_type == ResourceKind.DEPLOYMENT:
                async for batch in on_resync_deployments(kind):
                    yield batch
            elif resource_type == ResourceKind.POLICY:
                async for batch in on_resync_policies(kind):
                    yield batch
            elif resource_type == ResourceKind.USER:
                async for batch in on_resync_users(kind):
                    yield batch
    else:
        logger.warning(f"Unknown resource kind '{kind}' - returning empty result")
        return
