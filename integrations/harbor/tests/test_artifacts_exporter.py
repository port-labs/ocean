from typing import Any, AsyncIterator
from urllib.parse import unquote

import pytest

from integrations.harbor.exporters.artifacts import ArtifactsExporter


class _StubHarborClient:
    def __init__(
        self, pages_by_repository: dict[str, list[list[dict[str, Any]]]]
    ) -> None:
        self.pages_by_repository = pages_by_repository

    async def iter_pages(
        self, path: str, params: dict[str, Any] | None = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        repository_component = path.split("/repositories/")[-1].split("/artifacts")[0]
        repository = unquote(repository_component)
        for page in self.pages_by_repository.get(repository, []):
            yield page


@pytest.mark.asyncio
async def test_artifacts_exporter_maps_artifacts() -> None:
    client = _StubHarborClient(
        pages_by_repository={
            "alpha/library/nginx": [
                [
                    {
                        "digest": "sha256:123",
                        "type": "IMAGE",
                        "manifest_media_type": "application/vnd.oci.image.manifest.v1+json",
                        "creation_time": "2024-01-01T00:00:00Z",
                        "tags": [
                            {
                                "name": "latest",
                                "push_time": "2024-01-02T00:00:00Z",
                            }
                        ],
                        "labels": [{"name": "team:platform"}],
                        "scan_overview": {
                            "trivy": {
                                "severity": "HIGH",
                                "summary": {
                                    "critical": 1,
                                    "high": 3,
                                    "medium": 0,
                                    "low": 2,
                                    "negligible": 1,
                                },
                                "completion_time": "2024-01-03T00:00:00Z",
                            }
                        },
                    }
                ]
            ]
        }
    )

    exporter = ArtifactsExporter(
        client,
        repositories=[
            {"project_name": "alpha", "repository_path": "alpha/library/nginx"}
        ],
    )

    artifacts: list[dict[str, Any]] = []
    async for batch in exporter.iter_artifacts():
        artifacts.extend(batch)

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact["repository"] == "library/nginx"
    assert artifact["tag_count"] == 1
    assert artifact["primary_tag"] == "latest"
    assert artifact["media_type"].startswith("application/vnd.oci")
    assert artifact["labels"] == ["team:platform"]
    assert artifact["vulnerability_severity"] == "High"
    assert artifact["critical_vulnerability_count"] == 1
    assert artifact["high_vulnerability_count"] == 3
    assert artifact["scan_completed_at"].startswith("2024-01-03")


@pytest.mark.asyncio
async def test_artifacts_exporter_applies_filters() -> None:
    client = _StubHarborClient(
        pages_by_repository={
            "alpha/library/nginx": [
                [
                    {
                        "digest": "sha256:match",
                        "type": "IMAGE",
                        "manifest_media_type": "application/vnd.oci.image.manifest.v1+json",
                        "creation_time": "2024-02-01T00:00:00Z",
                        "tags": [{"name": "stable"}],
                        "labels": [{"name": "env:prod"}],
                        "scan_overview": {
                            "trivy": {
                                "severity": "critical",
                                "summary": {
                                    "critical": 1,
                                    "high": 0,
                                    "medium": 0,
                                    "low": 0,
                                    "negligible": 0,
                                },
                            }
                        },
                    },
                    {
                        "digest": "sha256:skip",
                        "type": "IMAGE",
                        "manifest_media_type": "application/vnd.oci.image.manifest.v1+json",
                        "creation_time": "2023-12-31T00:00:00Z",
                        "tags": [{"name": "old"}],
                        "labels": [{"name": "env:dev"}],
                        "scan_overview": {
                            "trivy": {
                                "severity": "low",
                                "summary": {
                                    "critical": 0,
                                    "high": 0,
                                    "medium": 0,
                                    "low": 1,
                                    "negligible": 0,
                                },
                            }
                        },
                    },
                ]
            ]
        }
    )

    exporter = ArtifactsExporter(
        client,
        repositories=[
            {"project_name": "alpha", "repository_path": "alpha/library/nginx"}
        ],
        tag_filter=["stable"],
        digest_filter=["sha256:match"],
        label_filter=["env:prod"],
        media_type_filter=["application/vnd.oci.image.manifest.v1+json"],
        created_since="2024-01-01T00:00:00Z",
        vuln_severity_at_least="High",
    )

    artifacts: list[dict[str, Any]] = []
    async for batch in exporter.iter_artifacts():
        artifacts.extend(batch)

    assert len(artifacts) == 1
    assert artifacts[0]["digest"] == "sha256:match"
