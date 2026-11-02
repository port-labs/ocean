from typing import Any

import pytest

import resync
from aws.core.exporters.cloudcontrol import CloudControlExporter
from aws.core.exporters.cloudcontrol.resource.models import (
    PaginatedCloudControlResourceRequest,
)
from aws.core.exporters.exporter_metadata import kind_to_export_metadata
from aws.core.helpers.types import ObjectKind
from integration import (
    AWSCustomKindResourceConfig,
    AWSResourceConfig,
    AWSResourceSelector,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)


def _minimal_port_mapping() -> PortResourceConfig:
    return PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier='."identifier"',
                title='."title"',
                blueprint='"testBlueprint"',
            )
        )
    )


def test_should_resync_via_cloud_control_false_for_first_class_kind() -> None:
    config = AWSResourceConfig(
        kind=ObjectKind.S3_BUCKET,
        selector=AWSResourceSelector(query="true"),
        port=_minimal_port_mapping(),
    )
    assert resync.should_resync_via_cloud_control(ObjectKind.S3_BUCKET, config) is False


def test_should_resync_via_cloud_control_false_for_unknown_first_class_config() -> None:
    config = AWSResourceConfig(
        kind="AWS::DoesNot::Exist",
        selector=AWSResourceSelector(query="true"),
        port=_minimal_port_mapping(),
    )
    assert (
        resync.should_resync_via_cloud_control("AWS::DoesNot::Exist", config) is False
    )


def test_should_resync_via_cloud_control_true_for_custom_kind_config() -> None:
    config = AWSCustomKindResourceConfig.parse_obj(
        {
            "kind": "AWS::IAM::Role",
            "selector": {"query": "true"},
            "port": _minimal_port_mapping().dict(),
        }
    )
    assert resync.should_resync_via_cloud_control("AWS::IAM::Role", config) is True


@pytest.mark.asyncio
async def test_resync_cloud_control_custom_kind_builds_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class _RecordingService:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

        def __aiter__(self) -> "_RecordingService":
            return self

        async def __anext__(self) -> Any:
            raise StopAsyncIteration

    monkeypatch.setattr(resync, "ResyncAWSService", _RecordingService)
    custom_config = AWSCustomKindResourceConfig.parse_obj(
        {
            "kind": "AWS::IAM::Role",
            "selector": {
                "query": "true",
                "useGetResourceAPI": True,
                "resourceScope": "global",
            },
            "port": _minimal_port_mapping().dict(),
        }
    )

    async for _ in resync.resync_cloud_control_custom_kind(
        "AWS::IAM::Role", custom_config
    ):
        pass

    assert len(calls) == 1
    assert calls[0]["kind"] == "AWS::IAM::Role"
    assert calls[0]["exporter_cls"] is CloudControlExporter
    assert calls[0]["request_cls"] is PaginatedCloudControlResourceRequest
    assert calls[0]["regional"] is False
    assert calls[0]["request_extras"] == {
        "type_name": "AWS::IAM::Role",
        "use_get_resource_api": True,
        "resource_scope": "global",
    }


def test_first_class_kind_still_in_exporter_metadata() -> None:
    assert ObjectKind.S3_BUCKET in kind_to_export_metadata
