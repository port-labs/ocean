from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock
import pytest

from aws.core.exporters.ecr.repository.actions import (
    DescribeRepositoriesAction,
    GetRepositoryPolicyAction,
    GetLifecyclePolicyAction,
    ListTagsForResourceAction,
    EcrRepositoryActionsMap,
)
from aws.core.interfaces.action import Action


class TestDescribeRepositoriesAction:

    @pytest.fixture
    def action(self) -> DescribeRepositoriesAction:
        return DescribeRepositoriesAction(AsyncMock())

    def test_inheritance(self, action: DescribeRepositoriesAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_returns_input(
        self, action: DescribeRepositoriesAction
    ) -> None:
        repositories = [
            {
                "repositoryName": "repo1",
                "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/repo1",
            },
            {
                "repositoryName": "repo2",
                "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/repo2",
            },
        ]
        assert await action.execute(repositories) == repositories


class TestGetRepositoryPolicyAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.get_repository_policy = AsyncMock()
        client.exceptions.RepositoryPolicyNotFoundException = Exception
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetRepositoryPolicyAction:
        return GetRepositoryPolicyAction(mock_client)

    def test_inheritance(self, action: GetRepositoryPolicyAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetRepositoryPolicyAction
    ) -> None:
        repositories = [
            {"repositoryName": "repo1"},
            {"repositoryName": "repo2"},
        ]

        policy_text_1 = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow"}]}'
        policy_text_2 = '{"Version":"2012-10-17","Statement":[{"Effect":"Deny"}]}'

        def mock_get_repository_policy(
            repositoryName: str, **kwargs: Any
        ) -> Dict[str, Any]:
            if repositoryName == "repo1":
                return {"policyText": policy_text_1}
            elif repositoryName == "repo2":
                return {"policyText": policy_text_2}
            return {"policyText": ""}

        action.client.get_repository_policy.side_effect = mock_get_repository_policy

        result = await action.execute(repositories)

        assert len(result) == 2
        assert result[0]["repositoryPolicy"] == policy_text_1
        assert result[1]["repositoryPolicy"] == policy_text_2
        assert action.client.get_repository_policy.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_policy_not_found(
        self, mock_logger: MagicMock, action: GetRepositoryPolicyAction
    ) -> None:
        repositories = [{"repositoryName": "repo-no-policy"}]

        action.client.get_repository_policy.side_effect = (
            action.client.exceptions.RepositoryPolicyNotFoundException(
                "Policy not found"
            )
        )

        result = await action.execute(repositories)

        assert len(result) == 1
        assert result[0]["repositoryPolicy"] is None


class TestGetLifecyclePolicyAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.get_lifecycle_policy = AsyncMock()
        client.exceptions.LifecyclePolicyNotFoundException = Exception
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> GetLifecyclePolicyAction:
        return GetLifecyclePolicyAction(mock_client)

    def test_inheritance(self, action: GetLifecyclePolicyAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_logger: MagicMock, action: GetLifecyclePolicyAction
    ) -> None:
        repositories = [
            {"repositoryName": "repo1"},
            {"repositoryName": "repo2"},
        ]

        lifecycle_text_1 = '{"rules":[{"rulePriority":1}]}'
        lifecycle_text_2 = '{"rules":[{"rulePriority":2}]}'

        def mock_get_lifecycle_policy(
            repositoryName: str, **kwargs: Any
        ) -> Dict[str, Any]:
            if repositoryName == "repo1":
                return {"lifecyclePolicyText": lifecycle_text_1}
            elif repositoryName == "repo2":
                return {"lifecyclePolicyText": lifecycle_text_2}
            return {"lifecyclePolicyText": ""}

        action.client.get_lifecycle_policy.side_effect = mock_get_lifecycle_policy

        result = await action.execute(repositories)

        assert len(result) == 2
        assert result[0]["lifecyclePolicy"] == lifecycle_text_1
        assert result[1]["lifecyclePolicy"] == lifecycle_text_2
        assert action.client.get_lifecycle_policy.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_policy_not_found(
        self, mock_logger: MagicMock, action: GetLifecyclePolicyAction
    ) -> None:
        repositories = [{"repositoryName": "repo-no-policy"}]

        action.client.get_lifecycle_policy.side_effect = (
            action.client.exceptions.LifecyclePolicyNotFoundException(
                "Policy not found"
            )
        )

        result = await action.execute(repositories)

        assert len(result) == 1
        assert result[0]["lifecyclePolicy"] is None


class TestListTagsForResourceAction:

    @pytest.fixture
    def mock_client(self) -> AsyncMock:
        client = AsyncMock()
        client.list_tags_for_resource = AsyncMock()
        return client

    @pytest.fixture
    def action(self, mock_client: AsyncMock) -> ListTagsForResourceAction:
        return ListTagsForResourceAction(mock_client)

    def test_inheritance(self, action: ListTagsForResourceAction) -> None:
        assert isinstance(action, Action)

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_logger: MagicMock, action: ListTagsForResourceAction
    ) -> None:
        repositories = [
            {
                "repositoryName": "repo1",
                "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/repo1",
            },
            {
                "repositoryName": "repo2",
                "repositoryArn": "arn:aws:ecr:us-east-1:123456789012:repository/repo2",
            },
        ]

        def mock_list_tags_for_resource(
            resourceArn: str, **kwargs: Any
        ) -> Dict[str, Any]:
            if "repo1" in resourceArn:
                return {"tags": [{"Key": "Environment", "Value": "prod"}]}
            elif "repo2" in resourceArn:
                return {"tags": [{"Key": "Environment", "Value": "dev"}]}
            return {"tags": []}

        action.client.list_tags_for_resource.side_effect = mock_list_tags_for_resource

        result = await action.execute(repositories)

        assert len(result) == 2
        assert result[0]["Tags"] == [{"Key": "Environment", "Value": "prod"}]
        assert result[1]["Tags"] == [{"Key": "Environment", "Value": "dev"}]
        assert action.client.list_tags_for_resource.call_count == 2


class TestEcrRepositoryActionsMap:

    @pytest.mark.asyncio
    async def test_merge_includes_defaults(self, mock_logger: MagicMock) -> None:
        action_map = EcrRepositoryActionsMap()
        merged = action_map.merge([])

        names = [cls.__name__ for cls in merged]
        assert "DescribeRepositoriesAction" in names

    @pytest.mark.asyncio
    async def test_merge_with_options(self, mock_logger: MagicMock) -> None:
        class DummyAction(Action):
            async def _execute(self, identifiers: List[Any]) -> List[Dict[str, Any]]:
                return [{"dummy": True}]

        EcrRepositoryActionsMap.options.append(DummyAction)
        try:
            action_map = EcrRepositoryActionsMap()
            merged = action_map.merge(["GetRepositoryPolicyAction", "DummyAction"])

            names = [cls.__name__ for cls in merged]
            assert "DescribeRepositoriesAction" in names
            assert "GetRepositoryPolicyAction" in names
            assert "DummyAction" in names
        finally:
            EcrRepositoryActionsMap.options = []
