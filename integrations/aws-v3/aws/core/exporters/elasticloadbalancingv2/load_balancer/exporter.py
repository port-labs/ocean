from typing import Any, AsyncGenerator, Type

from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.elasticloadbalancingv2.load_balancer.actions import (
    ElasticLoadBalancingV2ActionsMap,
)
from aws.core.exporters.elasticloadbalancingv2.load_balancer.models import LoadBalancer
from aws.core.exporters.elasticloadbalancingv2.load_balancer.models import (
    SingleLoadBalancerRequest,
    PaginatedLoadBalancerRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class ElasticLoadBalancingV2Exporter(IResourceExporter[list[dict[str, Any]]]):
    _service_name: SupportedServices = "elasticloadbalancing"
    _model_cls: Type[LoadBalancer] = LoadBalancer
    _actions_map: Type[ElasticLoadBalancingV2ActionsMap] = (
        ElasticLoadBalancingV2ActionsMap
    )

    async def get_resource(
        self, options: SingleLoadBalancerRequest
    ) -> dict[str, Any]:
        """Fetch detailed attributes of a single ELBv2 load balancer."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            response = await proxy.client.describe_load_balancers(  # type: ignore[attr-defined]
                LoadBalancerArns=[options.load_balancer_arn]
            )

            load_balancers = response.get("LoadBalancers", [])
            action_result = await inspector.inspect(
                load_balancers,
                options.include,
                extra_context={
                    "AccountId": options.account_id,
                    "Region": options.region,
                },
            )
            return action_result[0] if action_result else {}

    async def get_paginated_resources(
        self, options: PaginatedLoadBalancerRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all ELBv2 load balancers in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            paginator = proxy.get_paginator(
                "describe_load_balancers", "LoadBalancers"
            )

            async for load_balancers in paginator.paginate():
                if load_balancers:
                    action_result = await inspector.inspect(
                        load_balancers,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []
