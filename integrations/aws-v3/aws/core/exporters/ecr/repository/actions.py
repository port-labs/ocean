from typing import Any, Type
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import execute_concurrent_aws_operations


class GetRepositoryPolicyAction(Action[list[dict[str, Any]]]):
    """Fetches repository policy for ECR repositories."""

    async def _execute(
        self, repositories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:

        return await execute_concurrent_aws_operations(
            input_items=repositories,
            operation_func=self._fetch_repository_policy,
            get_resource_identifier=lambda repo: repo["repositoryName"],
            operation_name="repository policy",
        )

    async def _fetch_repository_policy(
        self, repository: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.get_repository_policy(
            repositoryName=repository["repositoryName"]
        )

        return {"repositoryPolicyText": response["policyText"]}


class GetLifecyclePolicyAction(Action[list[dict[str, Any]]]):
    """Fetches lifecycle policy for ECR repositories."""

    async def _execute(
        self, repositories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:

        return await execute_concurrent_aws_operations(
            input_items=repositories,
            operation_func=self._fetch_lifecycle_policy,
            get_resource_identifier=lambda repo: repo["repositoryName"],
            operation_name="lifecycle policy",
        )

    async def _fetch_lifecycle_policy(
        self, repository: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.get_lifecycle_policy(
            repositoryName=repository["repositoryName"]
        )
        return {"lifecyclePolicy": response}


class ListTagsForResourceAction(Action[list[dict[str, Any]]]):
    """Fetches tags for ECR repositories."""

    async def _execute(
        self, repositories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:

        return await execute_concurrent_aws_operations(
            input_items=repositories,
            operation_func=self._fetch_repository_tags,
            get_resource_identifier=lambda repo: repo["repositoryName"],
            operation_name="tags",
        )

    async def _fetch_repository_tags(
        self, repository: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.list_tags_for_resource(
            resourceArn=repository["repositoryArn"]
        )
        tags = response["tags"]
        return {"tags": tags}


class DescribeRepositoriesAction(Action[list[dict[str, Any]]]):
    """Process the initial list of repositories from AWS."""

    async def _execute(
        self, repositories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return repositories as-is"""
        return repositories


class EcrRepositoryActionsMap(ActionMap[list[dict[str, Any]]]):
    """Groups all actions for ECR repositories."""

    defaults: list[Type[Action[list[dict[str, Any]]]]] = [
        DescribeRepositoriesAction,
    ]
    options: list[Type[Action[list[dict[str, Any]]]]] = [
        GetRepositoryPolicyAction,
        GetLifecyclePolicyAction,
        ListTagsForResourceAction,
    ]
