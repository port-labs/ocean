from typing import Any, Dict, Literal
import pytest
from unittest.mock import AsyncMock, patch

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SinglePackageOptions
from github.helpers.utils import ObjectKind
from github.webhook.events import PACKAGE_UPSERT_EVENTS
from github.webhook.webhook_processors.package_webhook_processor import (
    PackageWebhookProcessor,
    is_ghcr_package,
)
from integration import GithubPackageConfig, GithubPackageSelector


@pytest.fixture
def resource_config() -> GithubPackageConfig:
    return _resource_config()


@pytest.fixture
def package_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> PackageWebhookProcessor:
    return PackageWebhookProcessor(event=mock_webhook_event)


def _package_payload(
    *,
    action: str = "published",
    package_type: str = "container",
    name: str = "hello_docker",
    include_organization: bool = True,
    owner_type: str = "Organization",
    registry_type: str | None = None,
    visibility: str | None = None,
) -> dict[str, Any]:
    package: dict[str, Any] = {
        "id": 197,
        "name": name,
        "package_type": package_type,
        "namespace": "test-org",
        "owner": {"login": "test-org", "type": owner_type},
    }
    if registry_type is not None:
        package["registry"] = {"type": registry_type, "url": "https://ghcr.io"}
    if visibility is not None:
        package["visibility"] = visibility

    payload: dict[str, Any] = {"action": action, "package": package}
    if include_organization:
        payload["organization"] = {"login": "test-org"}
    return payload


def _resource_config(
    *,
    visibility: Literal["public", "private", "internal"] | None = None,
) -> GithubPackageConfig:
    return GithubPackageConfig(
        kind=ObjectKind.PACKAGE,
        selector=GithubPackageSelector(query="true", visibility=visibility),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id | tostring",
                    title=".name",
                    blueprint='"githubPackage"',
                    properties={},
                )
            )
        ),
    )


class TestIsGhcrPackage:
    def test_rest_style_container_type(self) -> None:
        assert is_ghcr_package({"package_type": "container"}) is True

    def test_webhook_uppercase_container_type(self) -> None:
        assert is_ghcr_package({"package_type": "CONTAINER"}) is True

    def test_registry_type_fallback(self) -> None:
        assert (
            is_ghcr_package(
                {"package_type": "unknown", "registry": {"type": "CONTAINER"}}
            )
            is True
        )

    def test_legacy_docker_registry_excluded(self) -> None:
        assert is_ghcr_package({"package_type": "docker"}) is False


@pytest.mark.asyncio
class TestPackageWebhookProcessor:
    @pytest.mark.parametrize(
        "github_event,action,result",
        [
            ("package", PACKAGE_UPSERT_EVENTS[0], True),
            ("package", PACKAGE_UPSERT_EVENTS[1], True),
            ("package", "deleted", False),
            ("release", PACKAGE_UPSERT_EVENTS[0], False),
            ("invalid", "published", False),
        ],
    )
    async def test_should_process_event(
        self,
        package_webhook_processor: PackageWebhookProcessor,
        github_event: str,
        action: str,
        result: bool,
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"action": action},
            headers={"x-github-event": github_event},
        )
        event._original_request = AsyncMock()

        assert await package_webhook_processor._should_process_event(event) is result

    async def test_get_matching_kinds(
        self, package_webhook_processor: PackageWebhookProcessor
    ) -> None:
        kinds = await package_webhook_processor.get_matching_kinds(
            package_webhook_processor.event
        )
        assert kinds == [ObjectKind.PACKAGE]

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (_package_payload(), True),
            ({"action": "published"}, False),
            ({"package": {}}, False),
            (
                {
                    "package": {
                        "name": "hello_docker",
                        "owner": {"login": "octocat"},
                    }
                },
                True,
            ),
        ],
    )
    async def test_validate_payload(
        self,
        package_webhook_processor: PackageWebhookProcessor,
        payload: Dict[str, Any],
        expected: bool,
    ) -> None:
        result = await package_webhook_processor.validate_payload(payload)
        assert result is expected

    async def test_handle_event_upserts_ghcr_package(
        self,
        package_webhook_processor: PackageWebhookProcessor,
        resource_config: GithubPackageConfig,
    ) -> None:
        payload = _package_payload()
        expected_data = {
            "id": 197,
            "name": "hello_docker",
            "__organization": "test-org",
            "__image": "ghcr.io/test-org/hello_docker",
        }

        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = expected_data

        with patch(
            "github.webhook.webhook_processors.package_webhook_processor.RestPackageExporter",
            return_value=mock_exporter,
        ):
            result = await package_webhook_processor.handle_event(
                payload, resource_config
            )

        mock_exporter.get_resource.assert_called_once_with(
            SinglePackageOptions(
                organization="test-org",
                package_name="hello_docker",
                org_type="Organization",
                include_versions=False,
                max_versions=10,
            )
        )
        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == [expected_data]
        assert result.deleted_raw_results == []

    async def test_handle_event_skips_non_ghcr_package(
        self,
        package_webhook_processor: PackageWebhookProcessor,
        resource_config: GithubPackageConfig,
    ) -> None:
        payload = _package_payload(package_type="npm")

        with patch(
            "github.webhook.webhook_processors.package_webhook_processor.RestPackageExporter"
        ) as mock_exporter_cls:
            result = await package_webhook_processor.handle_event(
                payload, resource_config
            )

        mock_exporter_cls.assert_not_called()
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_event_returns_empty_when_package_missing(
        self,
        package_webhook_processor: PackageWebhookProcessor,
        resource_config: GithubPackageConfig,
    ) -> None:
        payload = _package_payload()
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = None

        with patch(
            "github.webhook.webhook_processors.package_webhook_processor.RestPackageExporter",
            return_value=mock_exporter,
        ):
            result = await package_webhook_processor.handle_event(
                payload, resource_config
            )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_event_user_owned_package(
        self,
        package_webhook_processor: PackageWebhookProcessor,
        resource_config: GithubPackageConfig,
    ) -> None:
        payload = _package_payload(include_organization=False, owner_type="User")
        payload["package"]["owner"] = {"login": "octocat", "type": "User"}
        expected_data = {
            "id": 197,
            "name": "hello_docker",
            "__organization": "octocat",
        }

        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = expected_data

        with patch(
            "github.webhook.webhook_processors.package_webhook_processor.RestPackageExporter",
            return_value=mock_exporter,
        ):
            result = await package_webhook_processor.handle_event(
                payload, resource_config
            )

        mock_exporter.get_resource.assert_called_once_with(
            SinglePackageOptions(
                organization="octocat",
                package_name="hello_docker",
                org_type="User",
                include_versions=False,
                max_versions=10,
            )
        )
        assert result.updated_raw_results == [expected_data]

    async def test_should_process_event_user_package_without_org_or_repo(
        self, package_webhook_processor: PackageWebhookProcessor
    ) -> None:
        ocean.integration_config["webhook_secret"] = ""
        payload = _package_payload(include_organization=False, owner_type="User")
        payload["package"]["owner"] = {"login": "octocat", "type": "User"}
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload=payload,
            headers={"x-github-event": "package"},
        )
        event._original_request = AsyncMock()

        assert await package_webhook_processor.should_process_event(event) is True

    async def test_should_process_event_user_package_with_null_repository(
        self, package_webhook_processor: PackageWebhookProcessor
    ) -> None:
        ocean.integration_config["webhook_secret"] = ""
        payload = _package_payload(include_organization=False, owner_type="User")
        payload["package"]["owner"] = {"login": "octocat", "type": "User"}
        payload["repository"] = None
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload=payload,
            headers={"x-github-event": "package"},
        )
        event._original_request = AsyncMock()

        assert await package_webhook_processor.should_process_event(event) is True

    async def test_handle_event_skips_visibility_mismatch_in_payload(
        self, package_webhook_processor: PackageWebhookProcessor
    ) -> None:
        payload = _package_payload(visibility="public")

        with patch(
            "github.webhook.webhook_processors.package_webhook_processor.RestPackageExporter"
        ) as mock_exporter_cls:
            result = await package_webhook_processor.handle_event(
                payload, _resource_config(visibility="private")
            )

        mock_exporter_cls.assert_not_called()
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_event_skips_visibility_mismatch_after_fetch(
        self, package_webhook_processor: PackageWebhookProcessor
    ) -> None:
        payload = _package_payload()
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = {
            "id": 197,
            "name": "hello_docker",
            "visibility": "public",
        }

        with patch(
            "github.webhook.webhook_processors.package_webhook_processor.RestPackageExporter",
            return_value=mock_exporter,
        ):
            result = await package_webhook_processor.handle_event(
                payload, _resource_config(visibility="private")
            )

        mock_exporter.get_resource.assert_called_once()
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_event_upserts_when_visibility_matches(
        self, package_webhook_processor: PackageWebhookProcessor
    ) -> None:
        payload = _package_payload(visibility="private")
        expected_data = {
            "id": 197,
            "name": "hello_docker",
            "visibility": "private",
        }
        mock_exporter = AsyncMock()
        mock_exporter.get_resource.return_value = expected_data

        with patch(
            "github.webhook.webhook_processors.package_webhook_processor.RestPackageExporter",
            return_value=mock_exporter,
        ):
            result = await package_webhook_processor.handle_event(
                payload, _resource_config(visibility="private")
            )

        mock_exporter.get_resource.assert_called_once()
        assert result.updated_raw_results == [expected_data]
