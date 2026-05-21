import asyncio
from typing import Any, AsyncGenerator, Mapping, Type

from loguru import logger

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

            image_ids = []
            if options.image_tag:
                image_ids.append({"imageTag": options.image_tag})
            if options.image_digest:
                image_ids.append({"imageDigest": options.image_digest})

            response = await proxy.client.describe_images(  # type: ignore[attr-defined]
                repositoryName=options.repository_name, imageIds=image_ids
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

            ecr_filter = {
                "tagStatus": options.tag_status,
                "imageStatus": options.image_status,
            }

            if options.repository_name:
                paginator = proxy.get_paginator("describe_images", "imageDetails")
                async for images in paginator.paginate(
                    repositoryName=options.repository_name, filter=ecr_filter
                ):
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
                repo_paginator = proxy.get_paginator(
                    "describe_repositories", "repositories"
                )
                async for repositories in repo_paginator.paginate():
                    if not repositories:
                        yield []
                        continue

                    all_images: list[list[dict[str, Any]] | BaseException] = (
                        await asyncio.gather(
                            *(
                                self._get_all_images(
                                    proxy, repo["repositoryName"], ecr_filter
                                )
                                for repo in repositories
                            ),
                            return_exceptions=True,
                        )
                    )
                    for repo_images in all_images:
                        if isinstance(repo_images, Exception):
                            logger.warning(
                                f"Failed to fetch images for repository: {repo_images}"
                            )
                            continue
                        if repo_images:
                            action_result = await inspector.inspect(
                                repo_images,
                                options.include,
                                extra_context={
                                    "AccountId": options.account_id,
                                    "Region": options.region,
                                },
                            )
                            yield action_result

    async def _get_all_images(
        self,
        proxy: AioBaseClientProxy,
        repo_name: str,
        ecr_filter: Mapping[str, str],
    ) -> list[dict[str, Any]]:
        images: list[dict[str, Any]] = []
        paginator = proxy.get_paginator("describe_images", "imageDetails")
        async for page in paginator.paginate(
            repositoryName=repo_name, filter=ecr_filter
        ):
            images.extend(page)
        return images
