import pytest

from coralogix.helpers.utils import required_permission, resolve_api_base_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://api.eu2.coralogix.com", "https://api.eu2.coralogix.com"),
        (
            "https://api.eu2.coralogix.com/mgmt/openapi/5",
            "https://api.eu2.coralogix.com",
        ),
        ("https://getport.app.eu2.coralogix.com/", "https://api.eu2.coralogix.com"),
        ("https://myteam.coralogix.com", "https://api.eu1.coralogix.com"),
        ("https://myteam.app.coralogix.us", "https://api.us1.coralogix.com"),
        ("https://myteam.app.cx498.coralogix.com", "https://api.us2.coralogix.com"),
        ("https://myteam.app.us3.coralogix.com", "https://api.us3.coralogix.com"),
        ("https://myteam.app.coralogix.in", "https://api.ap1.coralogix.com"),
        ("https://myteam.app.coralogixsg.com", "https://api.ap2.coralogix.com"),
        ("https://myteam.app.ap3.coralogix.com", "https://api.ap3.coralogix.com"),
        ("myteam.app.gov1.coralogixgov.us", "https://api.gov1.coralogixgov.us"),
    ],
)
def test_resolve_api_base_url(url: str, expected: str) -> None:
    assert resolve_api_base_url(url) == expected


def test_resolve_api_base_url_rejects_unknown_host() -> None:
    with pytest.raises(ValueError, match="Unrecognized Coralogix URL"):
        resolve_api_base_url("https://example.com")


@pytest.mark.parametrize(
    "endpoint,permission",
    [
        ("mgmt/openapi/5/slo/slos/v1", "SLO:READCONFIG"),
        ("/mgmt/openapi/5/alerts/alerts/v3", "ALERTS:READCONFIG"),
        ("mgmt/openapi/5/cases/cases/v1", "CASES:READ"),
        ("metrics/api/v1/query", "METRICS.DATA-API#HIGH:READDATA"),
        ("mgmt/openapi/5/aaa/identity/v1/whoami", None),
    ],
)
def test_required_permission(endpoint: str, permission: str | None) -> None:
    assert required_permission(endpoint) == permission
