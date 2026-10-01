from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def client():  # type: ignore[no-untyped-def]
    # Patch the shared HTTP client so constructing SonatypeClient does no I/O.
    with patch("sonatype.client.http_async_client", MagicMock()):
        from sonatype.client import SonatypeClient

        return SonatypeClient(
            base_url="https://iq.example.com",
            username="svc-port",
            token="token",
        )


APPLICATION = {
    "id": "app-internal-1",
    "publicId": "my-app",
    "name": "My App",
    "organizationId": "org-1",
}

REPORT_SUMMARY = {
    "stage": "release",
    "evaluationDate": "2026-01-01T00:00:00.000+0000",
    "reportHtmlUrl": "ui/links/application/my-app/report/rid1",
    "reportPdfUrl": "ui/links/application/my-app/report/rid1/pdf",
    "reportDataUrl": "api/v2/applications/app-internal-1/reports/rid1",
}

POLICY_REPORT = {
    "counts": {"totalComponentCount": 3},
    "components": [
        {
            "hash": "hashA",
            "packageUrl": "pkg:maven/g/a@1.0",
            "violations": [
                {
                    "policyId": "p1",
                    "policyName": "Security-Critical",
                    "policyThreatLevel": 9,
                },
                {
                    "policyId": "p2",
                    "policyName": "Security-Severe",
                    "policyThreatLevel": 5,
                },
            ],
        },
        {
            "hash": "hashB",
            "packageUrl": "pkg:maven/g/b@2.0",
            "violations": [
                {"policyId": "p3", "policyName": "Quality", "policyThreatLevel": 2},
            ],
        },
        {"hash": "hashC", "packageUrl": "pkg:maven/g/c@3.0", "violations": []},
    ],
}


def test_build_report_entity_counts(client) -> None:  # type: ignore[no-untyped-def]
    report = client._build_report_entity(APPLICATION, REPORT_SUMMARY, POLICY_REPORT)

    assert report["__identifier"] == "app-internal-1-release"
    assert report["__applicationId"] == "app-internal-1"
    assert report["__stage"] == "release"
    assert report["__criticalCount"] == 1
    assert report["__severeCount"] == 1
    assert report["__moderateCount"] == 1
    assert report["__lowCount"] == 0
    assert report["__componentsWithViolations"] == 2
    assert report["__totalComponents"] == 3
    assert (
        report["__url"]
        == "https://iq.example.com/ui/links/application/my-app/report/rid1"
    )


def test_build_violation_entities(client) -> None:  # type: ignore[no-untyped-def]
    violations = client._build_violation_entities(
        APPLICATION, REPORT_SUMMARY, POLICY_REPORT
    )

    assert len(violations) == 3
    first = violations[0]
    assert first["__identifier"] == "app-internal-1-release-hashA-p1"
    assert first["__applicationId"] == "app-internal-1"
    assert first["__reportIdentifier"] == "app-internal-1-release"
    assert first["__severity"] == "critical"
    assert first["__componentDisplayName"] == "pkg:maven/g/a@1.0"
    assert first["policyName"] == "Security-Critical"


def test_build_report_entity_handles_empty_policy_report(client) -> None:  # type: ignore[no-untyped-def]
    report = client._build_report_entity(APPLICATION, REPORT_SUMMARY, {})
    assert report["__criticalCount"] == 0
    assert report["__componentsWithViolations"] == 0
    assert report["__totalComponents"] is None


RAW_REPORT = {
    "components": [
        {
            "hash": "hashA",
            "packageUrl": "pkg:maven/g/a@1.0",
            "matchState": "exact",
            "componentIdentifier": {
                "format": "maven",
                "coordinates": {"groupId": "g", "artifactId": "a", "version": "1.0"},
            },
            "licenseData": {"effectiveLicenses": [{"licenseId": "Apache-2.0"}]},
            "dependencyData": {"directDependency": True},
            "securityData": {
                "securityIssues": [
                    {
                        "source": "cve",
                        "reference": "CVE-2021-44228",
                        "severity": 10.0,
                        "status": "Open",
                        "url": "https://nvd/CVE-2021-44228",
                        "threatCategory": "critical",
                    }
                ]
            },
        },
        {
            "hash": "hashB",
            "packageUrl": "pkg:maven/g/b@2.0",
            "componentIdentifier": {
                "format": "maven",
                "coordinates": {"groupId": "g", "artifactId": "b", "version": "2.0"},
            },
            "securityData": {"securityIssues": []},
        },
    ]
}


async def test_build_component_and_vulnerability_entities(client) -> None:  # type: ignore[no-untyped-def]
    data = await client._build_component_and_vulnerability_entities(
        APPLICATION, REPORT_SUMMARY, RAW_REPORT, include_remediation=False
    )

    components = data["components"]
    vulns = data["vulnerabilities"]

    assert len(components) == 2
    comp_a = components[0]
    assert comp_a["__identifier"] == "app-internal-1-release-hashA"
    assert comp_a["__version"] == "1.0"
    assert comp_a["__format"] == "maven"
    assert comp_a["__licenses"] == ["Apache-2.0"]
    assert comp_a["__maxCvssScore"] == 10.0
    assert comp_a["__securityIssueCount"] == 1
    assert comp_a["__cveReferences"] == ["CVE-2021-44228"]
    assert comp_a["__directDependency"] is True
    # remediation off -> no recommendation
    assert comp_a["recommendedVersion"] is None

    assert len(vulns) == 1
    cve = vulns[0]
    assert cve["__identifier"] == "CVE-2021-44228"
    assert cve["severity"] == "critical"
    assert cve["cvssScore"] == 10.0


async def test_vulnerability_severity_falls_back_to_cvss(client) -> None:  # type: ignore[no-untyped-def]
    """Unrecognized threatCategory must not block CVSS-based severity."""
    raw_report = {
        "components": [
            {
                "hash": "hashA",
                "packageUrl": "pkg:maven/g/a@1.0",
                "securityData": {
                    "securityIssues": [
                        {
                            "source": "cve",
                            "reference": "CVE-2099-0001",
                            "severity": 9.1,
                            "threatCategory": "unknown-category",
                        }
                    ]
                },
            }
        ]
    }
    data = await client._build_component_and_vulnerability_entities(
        APPLICATION, REPORT_SUMMARY, raw_report, include_remediation=False
    )
    assert data["vulnerabilities"][0]["severity"] == "critical"


async def test_build_components_with_remediation(client) -> None:  # type: ignore[no-untyped-def]
    from unittest.mock import AsyncMock

    client.get_component_remediation = AsyncMock(
        return_value={
            "recommendedVersion": "3.0.0",
            "recommendedRemediationType": "next-no-violations",
            "recommendedNonFailingVersion": "2.5.0",
        }
    )
    data = await client._build_component_and_vulnerability_entities(
        APPLICATION, REPORT_SUMMARY, RAW_REPORT, include_remediation=True
    )
    comp_a = data["components"][0]
    assert comp_a["recommendedVersion"] == "3.0.0"
    # component with no security issues should not trigger a remediation call
    client.get_component_remediation.assert_awaited_once()


async def test_get_application_source_control_configured(client) -> None:  # type: ignore[no-untyped-def]
    from unittest.mock import AsyncMock

    client._send_api_request = AsyncMock(
        return_value={
            "provider": "github",
            "repositoryUrl": "https://github.com/ajoanes98/auto-pr-example",
            "baseBranch": "main",
            "remediationPullRequestsEnabled": True,
        }
    )

    result = await client.get_application_source_control(APPLICATION)

    client._send_api_request.assert_awaited_once_with(
        "api/v2/sourceControl/application/app-internal-1"
    )
    assert result["__identifier"] == "app-internal-1"
    assert result["__applicationId"] == "app-internal-1"
    assert result["__githubRepository"] == "ajoanes98/auto-pr-example"
    # Prefer the application name so upserting via the sourceControl kind
    # does not rename the sonatypeApplication entity to its repo URL.
    assert result["__title"] == APPLICATION["name"]
    assert result["repositoryUrl"] == "https://github.com/ajoanes98/auto-pr-example"


async def test_get_application_source_control_not_configured(client) -> None:  # type: ignore[no-untyped-def]
    from unittest.mock import AsyncMock

    # _send_api_request already turns a 404 into {} — mirror that here.
    client._send_api_request = AsyncMock(return_value={})

    result = await client.get_application_source_control(APPLICATION)

    assert result is None


async def test_get_application_source_control_strips_token(client) -> None:  # type: ignore[no-untyped-def]
    from unittest.mock import AsyncMock

    client._send_api_request = AsyncMock(
        return_value={
            "provider": "github",
            "repositoryUrl": "https://github.com/ajoanes98/auto-pr-example",
            "token": "should-never-reach-the-catalog",
        }
    )

    result = await client.get_application_source_control(APPLICATION)

    assert "token" not in result


async def test_get_application_source_control_non_github_provider(client) -> None:  # type: ignore[no-untyped-def]
    from unittest.mock import AsyncMock

    client._send_api_request = AsyncMock(
        return_value={
            "provider": "bitbucket",
            "repositoryUrl": "https://bitbucket.org/ajoanes98/auto-pr-example",
        }
    )

    result = await client.get_application_source_control(APPLICATION)

    assert result["__githubRepository"] is None
    assert result["repositoryUrl"] == "https://bitbucket.org/ajoanes98/auto-pr-example"
