from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ecr.repository.actions import EcrRepositoryActionsMap
from aws.core.exporters.ecr.repository.models import Repository
from aws.core.exporters.ecr.repository.models import (
    SingleRepositoryRequest,
    PaginatedRepositoryRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector
from loguru import logger


class EcrRepositoryExporter(IResourceExporter):
    _service_name: SupportedServices = "ecr"
    _model_cls: Type[Repository] = Repository
    _actions_map: Type[EcrRepositoryActionsMap] = EcrRepositoryActionsMap

    async def get_resource(self, options: SingleRepositoryRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single ECR repository."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # Get repository details first
            try:
                response = await proxy.client.describe_repositories(
                    repositoryNames=[options.repository_name]
                )
                repositories = response.get("repositories", [])
                if not repositories:
                    return {}
                
                repo = repositories[0]
                repo_data = [{
                    "repositoryName": repo.get("repositoryName", ""),
                    "repositoryArn": repo.get("repositoryArn", ""),
                    "repositoryUri": repo.get("repositoryUri", ""),
                }]
                
                result = await inspector.inspect(repo_data, options.include)
                return result[0] if result else {}
                
            except Exception as e:
                logger.error(f"Error fetching repository {options.repository_name}: {e}")
                return {}

    async def get_paginated_resources(
        self, options: PaginatedRepositoryRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all ECR repositories in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )
            
            # Use the paginator for ECR repositories
            paginator = proxy.get_paginator("describe_repositories", "repositories")

            async for repositories in paginator.paginate():
                if repositories:
                    action_result = await inspector.inspect(
                        repositories,
                        options.include,
                        extra_context={
                            "AccountId": options.account_id,
                            "Region": options.region,
                        },
                    )
                    yield action_result
                else:
                    yield []