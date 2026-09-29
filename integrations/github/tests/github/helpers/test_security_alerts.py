from github.helpers.security_alerts import (
    enrich_security_alert_batch,
    is_alert_repo_archived,
    pop_org_alert_filters,
    repository_name_from_alert,
    security_alerts_list_url,
    should_include_org_alert,
)


def test_repository_name_from_alert() -> None:
    assert repository_name_from_alert({"repository": {"name": "ocean"}}) == "ocean"
    assert repository_name_from_alert({"repository": {}}) is None
    assert repository_name_from_alert({}) is None


def test_is_alert_repo_archived() -> None:
    assert is_alert_repo_archived({"repository": {"archived": True}}) is True
    assert is_alert_repo_archived({"repository": {"archived": False}}) is False
    assert is_alert_repo_archived({}) is False


def test_should_include_org_alert_filters() -> None:
    alert = {"repository": {"name": "repo-a", "archived": False}}
    assert (
        should_include_org_alert(alert, allowed_repos={"repo-a"}, exclude_archived=True)
        == "repo-a"
    )
    assert (
        should_include_org_alert(alert, allowed_repos={"repo-b"}, exclude_archived=True)
        is None
    )
    assert (
        should_include_org_alert(alert, allowed_repos=set(), exclude_archived=False)
        is None
    )

    archived = {"repository": {"name": "repo-a", "archived": True}}
    assert (
        should_include_org_alert(archived, allowed_repos=None, exclude_archived=True)
        is None
    )


def test_pop_org_alert_filters_preserves_empty_allowlist() -> None:
    allowed, exclude = pop_org_alert_filters(
        {"allowed_repos": [], "exclude_archived": True, "state": "open"}
    )
    assert allowed == set()
    assert exclude is True


def test_pop_org_alert_filters_none_means_unfiltered() -> None:
    allowed, exclude = pop_org_alert_filters({"state": "open"})
    assert allowed is None
    assert exclude is False


def test_security_alerts_list_url() -> None:
    assert (
        security_alerts_list_url(
            "https://api.github.com", "acme", "secret-scanning/alerts"
        )
        == "https://api.github.com/orgs/acme/secret-scanning/alerts"
    )
    assert (
        security_alerts_list_url(
            "https://api.github.com", "acme", "secret-scanning/alerts", "ocean"
        )
        == "https://api.github.com/repos/acme/ocean/secret-scanning/alerts"
    )


def test_enrich_security_alert_batch_filters_org_stream() -> None:
    alerts = [
        {"number": 1, "repository": {"name": "repo-a", "archived": False}},
        {"number": 2, "repository": {"name": "repo-b", "archived": True}},
    ]
    batch = enrich_security_alert_batch(
        alerts,
        organization="acme",
        allowed_repos={"repo-a", "repo-b"},
        exclude_archived=True,
    )
    assert len(batch) == 1
    assert batch[0]["__repository"] == "repo-a"
    assert batch[0]["__organization"] == "acme"
