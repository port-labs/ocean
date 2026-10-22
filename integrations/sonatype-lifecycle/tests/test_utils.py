import pytest

from utils import (
    build_component_identifier,
    build_report_identifier,
    build_violation_identifier,
    component_display_name,
    component_version,
    extract_report_id,
    normalize_severity,
    parse_github_owner_repo,
    pick_remediation_versions,
    severity_from_cvss,
    severity_from_threat_level,
    to_absolute_url,
)


@pytest.mark.parametrize(
    "level,expected",
    [
        (10, "critical"),
        (8, "critical"),
        (7, "severe"),
        (4, "severe"),
        (3, "moderate"),
        (2, "moderate"),
        (1, "low"),
        (0, "none"),
        (None, "none"),
    ],
)
def test_severity_from_threat_level(level: int | None, expected: str) -> None:
    assert severity_from_threat_level(level) == expected


def test_build_report_identifier() -> None:
    assert build_report_identifier("app123", "release") == "app123-release"


def test_build_violation_identifier() -> None:
    assert (
        build_violation_identifier("app123-release", "hashA", "polX")
        == "app123-release-hashA-polX"
    )


def test_component_display_name_prefers_package_url() -> None:
    component = {"packageUrl": "pkg:maven/g/a@1.0", "hash": "abc"}
    assert component_display_name(component) == "pkg:maven/g/a@1.0"


def test_component_display_name_from_coordinates() -> None:
    component = {
        "hash": "abc",
        "componentIdentifier": {
            "format": "maven",
            "coordinates": {
                "groupId": "tomcat",
                "artifactId": "tomcat-util",
                "version": "5.5.23",
            },
        },
    }
    assert component_display_name(component) == "tomcat : tomcat-util : 5.5.23"


def test_component_display_name_falls_back_to_hash() -> None:
    assert component_display_name({"hash": "abc"}) == "abc"


def test_extract_report_id_from_data_url() -> None:
    summary = {"reportDataUrl": "api/v2/applications/app/reports/rid123"}
    assert extract_report_id(summary) == "rid123"


def test_extract_report_id_none_when_missing() -> None:
    assert extract_report_id({}) is None


def test_to_absolute_url() -> None:
    assert (
        to_absolute_url("https://iq.example.com/", "ui/links/x")
        == "https://iq.example.com/ui/links/x"
    )
    assert (
        to_absolute_url("https://iq.example.com", "https://other/x")
        == "https://other/x"
    )
    assert to_absolute_url("https://iq.example.com", None) is None


def test_build_component_identifier() -> None:
    assert build_component_identifier("app", "release", "h1") == "app-release-h1"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("critical", "critical"),
        ("Severe", "severe"),
        ("high", "severe"),
        ("medium", "moderate"),
        ("unknown-word", "none"),
        (None, "none"),
    ],
)
def test_normalize_severity(value: str | None, expected: str) -> None:
    assert normalize_severity(value) == expected


@pytest.mark.parametrize(
    "score,expected",
    [
        (9.8, "critical"),
        (7.5, "severe"),
        (5.0, "moderate"),
        (1.2, "low"),
        (0, "none"),
        (None, "none"),
    ],
)
def test_severity_from_cvss(score: float | int | None, expected: str) -> None:
    assert severity_from_cvss(score) == expected


def test_component_version() -> None:
    component = {"componentIdentifier": {"coordinates": {"version": "1.2.3"}}}
    assert component_version(component) == "1.2.3"
    assert component_version({}) is None


def test_pick_remediation_versions() -> None:
    version_changes = [
        {
            "type": "next-non-failing",
            "data": {
                "component": {
                    "componentIdentifier": {"coordinates": {"version": "1.5.0"}}
                }
            },
        },
        {
            "type": "next-no-violations",
            "data": {
                "component": {
                    "componentIdentifier": {"coordinates": {"version": "2.0.0"}}
                }
            },
        },
    ]
    picked = pick_remediation_versions(version_changes)
    assert picked["recommendedVersion"] == "2.0.0"
    assert picked["recommendedRemediationType"] == "next-no-violations"
    assert picked["recommendedNonFailingVersion"] == "1.5.0"


def test_pick_remediation_versions_empty() -> None:
    picked = pick_remediation_versions([])
    assert picked["recommendedVersion"] is None
    assert picked["recommendedNonFailingVersion"] is None


@pytest.mark.parametrize(
    "repository_url,provider,expected",
    [
        (
            "https://github.com/ajoanes98/auto-pr-example",
            "github",
            ("ajoanes98", "auto-pr-example"),
        ),
        (
            "https://github.com/ajoanes98/auto-pr-example.git",
            "github",
            ("ajoanes98", "auto-pr-example"),
        ),
        (
            "https://github.com/ajoanes98/auto-pr-example/",
            "github",
            ("ajoanes98", "auto-pr-example"),
        ),
        (
            "git@github.com:ajoanes98/auto-pr-example.git",
            "github",
            ("ajoanes98", "auto-pr-example"),
        ),
        # Wrong/other provider: never guess, even if the URL happens to be a GitHub one.
        ("https://github.com/ajoanes98/auto-pr-example", "gitlab", (None, None)),
        ("https://github.com/ajoanes98/auto-pr-example", None, (None, None)),
        # Non-GitHub URL with provider=github: no match, no crash.
        ("https://gitlab.com/ajoanes98/auto-pr-example", "github", (None, None)),
        (None, "github", (None, None)),
        ("", "github", (None, None)),
    ],
)
def test_parse_github_owner_repo(
    repository_url: str | None,
    provider: str | None,
    expected: tuple[str | None, str | None],
) -> None:
    assert parse_github_owner_repo(repository_url, provider) == expected
