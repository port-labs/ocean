from github.probe.base_probe_flow import org_scopes


def test_org_scopes_omits_org_key_for_single_organization() -> None:
    assert org_scopes(["my-org"]) == [{}]


def test_org_scopes_includes_org_key_for_multiple_organizations() -> None:
    assert org_scopes(["org-a", "org-b"]) == [
        {"org": "org-a"},
        {"org": "org-b"},
    ]
