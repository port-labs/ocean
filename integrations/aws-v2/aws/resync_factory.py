from aws.helpers.paginator import AsyncPaginator
from aws.resources import (
    BaseResyncHandler,
    ResyncContext,
    SessionManagerProtocol,
    SQSResyncHandler,
    CloudControlResyncHandler,
    BotoDescribePaginatedHandler,
)
from typing import Any, AsyncIterator
import aioboto3
from overrides import AWSResourceConfig
from typing import TypedDict

class ElastiCacheCacheClusterQueryParams(TypedDict):
    __name__="AWS::ElastiCache::CacheCluster"

    service_name="elasticache"
    describe_method="describe_cache_clusters"
    list_param="CacheClusters"
    marker_param="Marker"

class ElasticLoadBalancingV2LoadBalancerQueryParams(TypedDict):
    __name__="AWS::ELBV2::LoadBalancer"

    service_name="elbv2"
    describe_method="describe_load_balancers"
    list_param="LoadBalancers"
    marker_param="NextMarker"

class ACMCertificateQueryParams(TypedDict):
    __name__="AWS::ACM::Certificate"

    service_name="acm"
    describe_method="list_certificates"
    list_param="CertificateSummaryList"
    marker_param="NextToken"

class CloudFormationStackQueryParams(TypedDict):
    __name__="AWS::CloudFormation::Stack"

    service_name="cloudformation"
    describe_method="list_stacks"
    list_param="Stacks"
    marker_param="NextToken"

class OrganizationsAccountQueryParams(TypedDict):
    __name__="AWS::Organizations::Account"

    service_name="organizations"
    describe_method="list_accounts"
    list_param="Accounts"
    marker_param="NextToken"



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
    ) -> BaseResyncHandler:
        ctx = ResyncContext(
            kind=kind,
            region=session.region_name,
            account_id=await self._sessions.get_account_id(session),
        )

        selector = resource_config.selector

        if kind == "AWS::SQS::Queue":
            return SQSResyncHandler(
                context=ctx,
                session=session,
                session_manager=self._sessions,
            )

        # Mapping for custom described kinds using TypedDict classes
        CUSTOM_DESCRIBE: dict[str, dict[str, Any]] = {
            "AWS::ElasticLoadBalancingV2::LoadBalancer": ElasticLoadBalancingV2LoadBalancerQueryParams,
            "AWS::ElastiCache::CacheCluster": ElastiCacheCacheClusterQueryParams,
            "AWS::ACM::Certificate": ACMCertificateQueryParams,
            "AWS::CloudFormation::Stack": CloudFormationStackQueryParams,
            "AWS::Organizations::Account": OrganizationsAccountQueryParams,
        }

        if kind in CUSTOM_DESCRIBE:
            params = CUSTOM_DESCRIBE[kind]
            return BotoDescribePaginatedHandler(
                context=ctx,
                session=session,
                session_manager=self._sessions,
                service_name=params["service_name"],
                describe_method=params["describe_method"],
                list_param=params["list_param"],
                marker_param=params["marker_param"],
            )

        # Fallback to CloudControl
        return CloudControlResyncHandler(
            context=ctx,
            session=session,
            session_manager=self._sessions,
            use_get_resource_api=selector.use_get_resource_api,
        )

async def resync(
    *,
    kind: str,
    account_id: str | None,
    region: str | None,
    resource_config: "AWSResourceConfig",
    session_manager
) -> AsyncIterator[list[dict[str, Any]]]:
    """High‑level helper that hides strategy lookup & session iteration."""

    factory = ResyncStrategyFactory(
        session_manager=session_manager,
    )

    async for session in session_manager.iter_sessions(account_id, region):
        resync_handler = await factory.create(
            kind=kind, session=session, resource_config=resource_config
        )
        async for batch in resync_handler:
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
