"""Pure helper functions for the Sonatype Lifecycle integration.

Keeping these free of I/O makes them trivial to unit test and keeps the
API client and webhook processors focused on orchestration.
"""

import re
from typing import Any

# Sonatype IQ expresses risk as a "policy threat level" on a 0-10 scale.
# The IQ UI groups those levels into named severities; we mirror that grouping
# so the catalog shows the same language operators see in Sonatype.
#   8-10 -> Critical, 4-7 -> Severe, 2-3 -> Moderate, 1 -> Low, 0 -> None
SEVERITY_CRITICAL = "critical"
SEVERITY_SEVERE = "severe"
SEVERITY_MODERATE = "moderate"
SEVERITY_LOW = "low"
SEVERITY_NONE = "none"


def severity_from_threat_level(threat_level: int | float | None) -> str:
    """Map a numeric IQ threat level (0-10) to a named severity bucket."""
    if threat_level is None:
        return SEVERITY_NONE
    level = int(threat_level)
    if level >= 8:
        return SEVERITY_CRITICAL
    if level >= 4:
        return SEVERITY_SEVERE
    if level >= 2:
        return SEVERITY_MODERATE
    if level >= 1:
        return SEVERITY_LOW
    return SEVERITY_NONE


def build_report_identifier(application_id: str, stage: str) -> str:
    """A stable identifier for a report entity.

    We key the report entity on ``<applicationInternalId>-<stage>`` rather than
    on the volatile per-scan ``reportId``. This means the catalog holds one
    "release report", one "build report" etc. per application, and each new scan
    updates that same entity in place instead of piling up historical entities.
    """
    return f"{application_id}-{stage}"


def build_violation_identifier(
    report_identifier: str, component_hash: str, policy_id: str
) -> str:
    """A deterministic identifier for a single policy violation.

    Using the stable ``<applicationId>-<stage>`` report identifier (not the
    volatile per-scan ``reportId``) with the (component, policy) pair means a
    re-scan updates existing violations in place, and violations that are
    fixed/waived simply stop appearing and are pruned by Ocean at the end of
    the resync.
    """
    return f"{report_identifier}-{component_hash}-{policy_id}"


def component_display_name(component: dict[str, Any]) -> str:
    """Build a human-readable component name.

    Prefers the packageUrl (PURL) when present, otherwise assembles a name from
    the component coordinates (e.g. ``groupId : artifactId : version``).
    """
    package_url = component.get("packageUrl")
    if package_url:
        return package_url

    # Use `or {}` (not .get(key, {})) because IQ can return these keys with an
    # explicit null value for unmatched/unknown components, and .get's default
    # only applies when the key is absent.
    identifier = component.get("componentIdentifier") or {}
    coordinates = identifier.get("coordinates") or {}
    if not coordinates:
        return component.get("hash", "unknown-component")

    # Different ecosystems use different coordinate keys; join whatever is set.
    ordered_keys = ["groupId", "artifactId", "packageId", "name", "version"]
    parts = [str(coordinates[key]) for key in ordered_keys if coordinates.get(key)]
    return " : ".join(parts) if parts else component.get("hash", "unknown-component")


def build_component_identifier(
    application_id: str, stage: str, component_hash: str
) -> str:
    """A stable identifier for a component-in-a-report entity.

    Keyed on ``<applicationInternalId>-<stage>-<componentHash>`` so it tracks
    the report-per-stage model: a component updates in place across scans and is
    pruned when it no longer appears in that application's stage report.
    """
    return f"{application_id}-{stage}-{component_hash}"


def normalize_severity(value: str | None) -> str:
    """Normalize a Sonatype severity/threat-category word to our enum.

    Sonatype security issues carry a ``threatCategory`` that is already a
    severity word (e.g. "critical", "severe"); we map it onto our five buckets
    and default unknown values to "none".
    """
    if not value:
        return SEVERITY_NONE
    lowered = value.strip().lower()
    if lowered in {
        SEVERITY_CRITICAL,
        SEVERITY_SEVERE,
        SEVERITY_MODERATE,
        SEVERITY_LOW,
        SEVERITY_NONE,
    }:
        return lowered
    # Some responses use "high"/"medium" wording; fold those in sensibly.
    aliases = {"high": SEVERITY_SEVERE, "medium": SEVERITY_MODERATE}
    return aliases.get(lowered, SEVERITY_NONE)


def severity_from_cvss(score: float | int | None) -> str:
    """Derive a severity bucket from a CVSS score (0-10) when no category set."""
    if score is None:
        return SEVERITY_NONE
    if score >= 9:
        return SEVERITY_CRITICAL
    if score >= 7:
        return SEVERITY_SEVERE
    if score >= 4:
        return SEVERITY_MODERATE
    if score > 0:
        return SEVERITY_LOW
    return SEVERITY_NONE


def component_version(component: dict[str, Any]) -> str | None:
    """Extract the version string from a component's coordinates."""
    identifier = component.get("componentIdentifier") or {}
    coordinates = identifier.get("coordinates") or {}
    return coordinates.get("version")


# Component Remediation "versionChanges" types, in priority order. We surface
# the first available "no violations" fix as the recommended upgrade, and the
# first "non failing" version as a softer fallback.
REMEDIATION_NO_VIOLATIONS_TYPES = [
    "next-no-violations",
    "next-no-violations-with-dependencies",
]
REMEDIATION_NON_FAILING_TYPES = [
    "next-non-failing",
    "next-non-failing-with-dependencies",
]


def pick_remediation_versions(
    version_changes: list[dict[str, Any]],
) -> dict[str, str | None]:
    """Reduce a remediation ``versionChanges`` list to recommended versions.

    ``recommendedVersion`` mirrors the single "Suggested Version Change" that the
    IQ UI surfaces for a component at a given stage: it prefers a version that
    clears *all* violations (``next-no-violations``) but falls back to the next
    version with no *failing* violations (``next-non-failing``) when no fully
    clean upgrade exists. This matters because many components — and notably the
    source (SCM) stage, whose suggestion is labelled "next version with no Source
    failure" — only ever return a non-failing recommendation. Without this
    fallback ``recommendedVersion`` would be blank even though IQ has a fix.

    ``recommendedNonFailingVersion`` is retained separately so consumers can still
    distinguish the non-failing option, and ``recommendedRemediationType`` records
    which type ``recommendedVersion`` came from.
    """

    def version_for(types: list[str]) -> tuple[str | None, str | None]:
        for change_type in types:
            for change in version_changes:
                if change.get("type") == change_type:
                    component = (change.get("data") or {}).get("component") or {}
                    return component_version(component), change_type
        return None, None

    no_violations, no_violations_type = version_for(REMEDIATION_NO_VIOLATIONS_TYPES)
    non_failing, non_failing_type = version_for(REMEDIATION_NON_FAILING_TYPES)

    # Prefer the strongest available fix, but fall back to the non-failing one.
    recommended: str | None
    recommended_type: str | None
    if no_violations is not None:
        recommended, recommended_type = no_violations, no_violations_type
    else:
        recommended, recommended_type = non_failing, non_failing_type

    return {
        "recommendedVersion": recommended,
        "recommendedRemediationType": recommended_type,
        "recommendedNonFailingVersion": non_failing,
    }


def extract_report_id(report_summary: dict[str, Any]) -> str | None:
    """Pull the per-scan reportId out of a report-summary object.

    The reports endpoint returns URLs but not a bare reportId, so we recover it
    from the path segment following ``/reports/`` or ``/report/``. Parsing by
    that separator (rather than taking the last path segment) keeps us correct
    even when the URL has a trailing action like ``/raw`` or ``/pdf``, e.g.
    ``api/v2/applications/<publicId>/reports/<reportId>/raw`` -> ``<reportId>``.
    """
    for url_key in ("reportDataUrl", "reportHtmlUrl", "latestReportHtmlUrl"):
        url = report_summary.get(url_key)
        if not url:
            continue
        for separator in ("/reports/", "/report/"):
            if separator in url:
                return url.split(separator, 1)[1].split("/")[0]
    return None


def to_absolute_url(base_url: str, relative_url: str | None) -> str | None:
    """Turn an IQ-relative UI/API path into an absolute URL for the catalog."""
    if not relative_url:
        return None
    if relative_url.startswith("http://") or relative_url.startswith("https://"):
        return relative_url
    return f"{base_url.rstrip('/')}/{relative_url.lstrip('/')}"


def read_stages(selector: Any) -> list[str]:
    """Read the optional ``stages`` filter from a resource-config selector.

    Read by attribute name rather than via ``isinstance`` against our selector
    subclass: Ocean's config parsing (and flat-layout module identity) means the
    runtime selector is not always a literal instance of our subclass, so an
    ``isinstance`` check can silently miss a configured value.
    """
    return list(getattr(selector, "stages", []) or [])


def read_include_remediation(selector: Any) -> bool:
    """Whether to fetch remediation, read by attribute name (not ``isinstance``).

    The runtime selector may not be a literal ``ComponentSelector`` instance, so
    we read ``include_remediation`` directly and coerce to bool. Reading via
    ``isinstance`` previously disabled remediation even when the config set
    ``includeRemediation: true``.
    """
    return bool(getattr(selector, "include_remediation", False))


# Matches github.com/{owner}/{repo}, both HTTPS (with or without a trailing
# ".git") and the SSH-style "git@github.com:owner/repo.git" form. Per
# Sonatype's docs, IQ Server normalizes any SSH URL it's given to HTTPS on
# save, but we accept both shapes defensively rather than assume that always
# happened before our read.
_GITHUB_URL_PATTERN = re.compile(
    r"github\.com[:/]+(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def parse_github_owner_repo(
    repository_url: str | None, provider: str | None
) -> tuple[str | None, str | None]:
    """Extract ``(owner, repo)`` from an IQ Source Control ``repositoryUrl``.

    Only attempts extraction when ``provider`` is ``"github"`` — this is
    intentionally scoped to GitHub for now since that's the only source
    control target Port relates to today (via the ``githubRepository``
    blueprint). GitLab/Bitbucket/Azure DevOps repos configured in IQ are left
    unparsed rather than guessed at, so a future GitLab relation isn't
    modeled prematurely. Returns ``(None, None)`` if the URL doesn't match the
    expected shape (e.g. a self-hosted GitHub Enterprise domain).
    """
    if not repository_url or (provider or "").strip().lower() != "github":
        return None, None
    match = _GITHUB_URL_PATTERN.search(repository_url.strip())
    if not match:
        return None, None
    return match.group("owner"), match.group("repo")
