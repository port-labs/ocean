from typing import Any, Type, cast
from aws.core.interfaces.action import Action, ActionMap
from aws.core.helpers.utils import is_recoverable_aws_exception
from loguru import logger
import asyncio


class GetRepositoryPolicyAction(Action):
    """Fetches repository policy for ECR repositories."""

    async def _execute(
        self, repositories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not repositories:
            return []

        policies = await asyncio.gather(
            *(self._fetch_repository_policy(repo) for repo in repositories),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, policy_result in enumerate(policies):
            if isinstance(policy_result, Exception):
                repository_name = repositories[idx].get("repositoryName", "unknown")
                if is_recoverable_aws_exception(policy_result):
                    logger.warning(
                        f"Skipping repository policy for '{repository_name}': {policy_result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching repository policy for '{repository_name}': {policy_result}"
                    )
                    raise policy_result
            results.append(cast(dict[str, Any], policy_result))

        logger.info(
            f"Successfully fetched policies for {len(results)} ECR repositories"
        )
        return results

    async def _fetch_repository_policy(
        self, repository: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            response = await self.client.get_repository_policy(
                repositoryName=repository["repositoryName"]
            )
            return {"repositoryPolicy": response["policyText"]}
        except self.client.exceptions.RepositoryPolicyNotFoundException:
            return {"repositoryPolicy": None}


class GetLifecyclePolicyAction(Action):
    """Fetches lifecycle policy for ECR repositories."""

    async def _execute(
        self, repositories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not repositories:
            return []

        policies = await asyncio.gather(
            *(self._fetch_lifecycle_policy(repo) for repo in repositories),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, policy_result in enumerate(policies):
            if isinstance(policy_result, Exception):
                repository_name = repositories[idx].get("repositoryName", "unknown")
                if is_recoverable_aws_exception(policy_result):
                    logger.warning(
                        f"Skipping lifecycle policy for '{repository_name}': {policy_result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching lifecycle policy for '{repository_name}': {policy_result}"
                    )
                    raise policy_result
            results.append(cast(dict[str, Any], policy_result))

        logger.info(
            f"Successfully fetched lifecycle policies for {len(results)} ECR repositories"
        )
        return results

    async def _fetch_lifecycle_policy(
        self, repository: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            response = await self.client.get_lifecycle_policy(
                repositoryName=repository["repositoryName"]
            )
            return {"lifecyclePolicy": response["lifecyclePolicyText"]}
        except self.client.exceptions.LifecyclePolicyNotFoundException:
            return {"lifecyclePolicy": None}


class ListTagsForResourceAction(Action):
    """Fetches tags for ECR repositories."""

    async def _execute(
        self, repositories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not repositories:
            return []

        tags = await asyncio.gather(
            *(self._fetch_repository_tags(repo) for repo in repositories),
            return_exceptions=True,
        )

        results: list[dict[str, Any]] = []
        for idx, tag_result in enumerate(tags):
            if isinstance(tag_result, Exception):
                repository_name = repositories[idx].get("repositoryName", "unknown")
                if is_recoverable_aws_exception(tag_result):
                    logger.warning(
                        f"Skipping tags for repository '{repository_name}': {tag_result}"
                    )
                    continue
                else:
                    logger.error(
                        f"Error fetching tags for repository '{repository_name}'"
                    )
                    raise tag_result
            results.append(cast(dict[str, Any], tag_result))

        logger.info(f"Successfully fetched tags for {len(results)} ECR repositories")
        return results

    async def _fetch_repository_tags(
        self, repository: dict[str, Any]
    ) -> dict[str, Any]:
        response = await self.client.list_tags_for_resource(
            resourceArn=repository["repositoryArn"]
        )
        tags = response["tags"]
        return {"Tags": tags}


class DescribeRepositoriesAction(Action):
    """Process the initial list of repositories from AWS."""

    async def _execute(
        self, repositories: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Return repositories as-is"""
        return repositories


class EcrRepositoryActionsMap(ActionMap):
    """Groups all actions for ECR repositories."""

    defaults: list[Type[Action]] = [
        DescribeRepositoriesAction,
    ]
    options: list[Type[Action]] = [
        GetRepositoryPolicyAction,
        GetLifecyclePolicyAction,
        ListTagsForResourceAction,
    ]
