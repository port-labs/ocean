from typing import Any, AsyncGenerator, Type
from aws.core.client.proxy import AioBaseClientProxy
from aws.core.exporters.ecr.image.actions import EcrImageActionsMap
from aws.core.exporters.ecr.image.models import Image
from aws.core.exporters.ecr.image.models import (
    SingleImageRequest,
    PaginatedImageRequest,
)
from aws.core.helpers.types import SupportedServices
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.modeling.resource_inspector import ResourceInspector


class EcrImageExporter(IResourceExporter):
    _service_name: SupportedServices = "ecr"
    _model_cls: Type[Image] = Image
    _actions_map: Type[EcrImageActionsMap] = EcrImageActionsMap

    async def get_resource(self, options: SingleImageRequest) -> dict[str, Any]:
        """Fetch detailed attributes of a single ECR image."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            # Build imageIds filter based on provided parameters
            image_ids = []
            if options.image_tag:
                image_ids.append({"imageTag": options.image_tag})
            if options.image_digest:
                image_ids.append({"imageDigest": options.image_digest})
            
            # If neither tag nor digest provided, get latest
            if not image_ids:
                image_ids.append({"imageTag": "latest"})

            response = await proxy.client.describe_images(  # type: ignore[attr-defined]
                repositoryName=options.repository_name,
                imageIds=image_ids
            )
            images = response["imageDetails"]
            if not images:
                return {}

            result = await inspector.inspect(images, options.include)
            return result[0] if result else {}

    async def get_paginated_resources(
        self, options: PaginatedImageRequest
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all ECR images in a region."""
        async with AioBaseClientProxy(
            self.session, options.region, self._service_name
        ) as proxy:
            inspector = ResourceInspector(
                proxy.client, self._actions_map(), lambda: self._model_cls()
            )

            # If repository_name is specified, only fetch images from that repository
            if options.repository_name:
                paginator = proxy.get_paginator("describe_images", "imageDetails")
                async for images in paginator.paginate(repositoryName=options.repository_name):
                    if images:
                        action_result = await inspector.inspect(
                            images,
                            options.include,
                            extra_context={
                                "AccountId": options.account_id,
                                "Region": options.region,
                            },
                        )
                        yield action_result
                    else:
                        yield []
            else:
                # Fetch images from all repositories in the region
                # First get all repositories
                repo_paginator = proxy.get_paginator("describe_repositories", "repositories")
                async for repositories in repo_paginator.paginate():
                    if repositories:
                        for repository in repositories:
                            repo_name = repository["repositoryName"]
                            image_paginator = proxy.get_paginator("describe_images", "imageDetails")
                            async for images in image_paginator.paginate(repositoryName=repo_name):
                                if images:
                                    action_result = await inspector.inspect(
                                        images,
                                        options.include,
                                        extra_context={
                                            "AccountId": options.account_id,
                                            "Region": options.region,
                                        },
                                    )
                                    yield action_result
                                else:
                                    yield []
                    else:
                        yield []