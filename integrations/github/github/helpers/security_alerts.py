from typing import Any, Optional, cast

from github.helpers.models import SecurityAlert
from github.helpers.utils import enrich_with_organization, enrich_with_repository


def repository_name_from_alert(alert: SecurityAlert) -> Optional[str]:
    """Return the repository name embedded on an org-level security alert."""
    repository = alert.get("repository")
    if isinstance(repository, dict):
        name = repository.get("name")
        if isinstance(name, str) and name:
            return name
    return None


def is_alert_repo_archived(alert: SecurityAlert) -> bool:
    """Return whether the alert's repository is archived (org-level payloads)."""
    repository = alert.get("repository")
    if isinstance(repository, dict):
        return bool(repository.get("archived"))
    return False


def should_include_org_alert(
    alert: SecurityAlert,
    *,
    allowed_repos: Optional[set[str]] = None,
    exclude_archived: bool = False,
) -> Optional[str]:
    """Return repo name if the alert should be synced, otherwise ``None``."""
    repo_name = repository_name_from_alert(alert)
    if not repo_name:
        return None
    if allowed_repos is not None and repo_name not in allowed_repos:
        return None
    if exclude_archived and is_alert_repo_archived(alert):
        return None
    return repo_name


def security_alerts_list_url(
    base_url: str,
    organization: str,
    resource: str,
    repo_name: Optional[str] = None,
) -> str:
    """Build repo- or org-level list URL for a security-alerts resource path."""
    if repo_name:
        return f"{base_url}/repos/{organization}/{repo_name}/{resource}"
    return f"{base_url}/orgs/{organization}/{resource}"


def pop_org_alert_filters(
    params: dict[str, Any],
) -> tuple[Optional[set[str]], bool]:
    """Pop org-level filter fields from request params.

    ``allowed_repos`` uses ``is not None`` so an empty allowlist (repoSearch
    matched nothing) stays empty and does not fall through to "no filter".
    """
    allowed_repos_list = params.pop("allowed_repos", None)
    exclude_archived = bool(params.pop("exclude_archived", False))
    allowed_repos = set(allowed_repos_list) if allowed_repos_list is not None else None
    return allowed_repos, exclude_archived


def enrich_security_alert_batch(
    alerts: list[dict[str, Any]],
    *,
    organization: str,
    repo_name: Optional[str] = None,
    allowed_repos: Optional[set[str]] = None,
    exclude_archived: bool = False,
) -> list[SecurityAlert]:
    """Enrich alerts with ``__repository`` / ``__organization``, filtering org streams."""
    batch: list[SecurityAlert] = []
    for raw in alerts:
        alert = cast(SecurityAlert, raw)
        name = (
            repo_name
            if repo_name
            else should_include_org_alert(
                alert,
                allowed_repos=allowed_repos,
                exclude_archived=exclude_archived,
            )
        )
        if not name:
            continue
        batch.append(
            cast(
                SecurityAlert,
                enrich_with_organization(enrich_with_repository(raw, name), organization),
            )
        )
    return batch
