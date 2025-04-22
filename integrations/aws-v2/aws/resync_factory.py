from aws.helpers.paginator import AsyncPaginator
from aws.resources import (
    BaseResyncStrategy,
    ResyncContext,
    SessionManagerProtocol,
    SQSResyncStrategy,
    CloudControlResyncStrategy,
    BotoDescribePaginatedStrategy,
)
from typing import Any, AsyncIterator
import aioboto3
from overrides import AWSResourceConfig


class ResyncStrategyFactory:
    """Return the appropriate strategy given *kind* & *resource_config*."""

    def __init__(
        self,
        *,
        session_manager: SessionManagerProtocol,
    ) -> None:
        self._sessions = session_manager

    async def create(
        self,
        *,
        kind: str,
        session: aioboto3.Session,
        resource_config: "AWSResourceConfig",
    ) -> BaseResyncStrategy:
        ctx = ResyncContext(
            kind=kind,
            region=session.region_name,
            account_id=await self._sessions.get_account_id(session),
        )

        selector = resource_config.selector  # expected attr → bool flags etc.

        if kind == "AWS::SQS::Queue":
            return SQSResyncStrategy(
                context=ctx,
                session=session,
                session_manager=self._sessions,
            )

        # Example mapping for a few custom described kinds – make configurable.
        CUSTOM_DESCRIBE: dict[str, dict[str, Any]] = {
            "AWS::ElasticLoadBalancingV2::LoadBalancer": dict(
                service_name="elbv2",
                describe_method="describe_load_balancers",
                list_param="LoadBalancers",
                marker_param="NextMarker",
            ),
            "AWS::ElastiCache::CacheCluster": dict(
                service_name="elasticache",
                describe_method="describe_cache_clusters",
                list_param="CacheClusters",
                marker_param="Marker",
            ),
        }
        if kind in CUSTOM_DESCRIBE:
            return BotoDescribePaginatedStrategy(
                context=ctx,
                session=session,
                session_manager=self._sessions,
                **CUSTOM_DESCRIBE[kind],
            )

        # Fallback to CloudControl
        return CloudControlResyncStrategy(
            context=ctx,
            session=session,
            session_manager=self._sessions,
            use_get_resource_api=selector.use_get_resource_api,
        )


# ---------------------------------------------------------------------------
# Public façade – what the caller uses.
# ---------------------------------------------------------------------------


async def resync(
    *,
    kind: str,
    account_id: str | None,
    region: str | None,
    resource_config: "AWSResourceConfig",
    session_manager: SessionManagerProtocol,
) -> AsyncIterator[list[dict[str, Any]]]:
    """High‑level helper that hides strategy lookup & session iteration."""

    factory = ResyncStrategyFactory(
        session_manager=session_manager,
    )

    async for session in session_manager.iter_sessions(account_id, region):
        strategy = await factory.create(
            kind=kind, session=session, resource_config=resource_config
        )
        async for batch in strategy:
            yield batch


# ---------------------------------------------------------------------------
# Example usage (would live in your orchestration layer / CLI / Lambda entrypoint)
# ---------------------------------------------------------------------------

# async def handler(event, context):
#     async for batch in resync(
#         kind="AWS::SQS::Queue",
#         account_id=event.get("account_id"),
#         region=event.get("region"),
#         resource_config=AWSResourceConfig(...),
#         session_manager=_session_manager,
#         paginator_factory=AsyncPaginator,
#     ):
#         process(batch)
