"""Tests for resolve_next_link_url helper"""

from http_server.helpers.utils import resolve_next_link_url


class TestResolveNextLinkUrl:
    def test_absolute_https_url_unchanged(self) -> None:
        next_url = "https://graph.example.com/v1.0/items?$skiptoken=abc"
        base_url = "https://graph.example.com/v1.0"
        assert resolve_next_link_url(next_url, base_url) == next_url

    def test_absolute_http_url_unchanged(self) -> None:
        next_url = "http://api.example.com/items?page=2"
        base_url = "http://api.example.com"
        assert resolve_next_link_url(next_url, base_url) == next_url

    def test_absolute_url_case_insensitive_scheme(self) -> None:
        next_url = "HTTPS://graph.example.com/v1.0/items?$skiptoken=abc"
        base_url = "https://graph.example.com/v1.0"
        assert resolve_next_link_url(next_url, base_url) == next_url

    def test_relative_path_appended_to_gateway_base_url(self) -> None:
        base_url = "https://api.example.com/ex/tenant/cloud-id-123"
        next_url = "/wiki/api/v2/spaces?cursor=xyz"
        assert (
            resolve_next_link_url(next_url, base_url)
            == "https://api.example.com/ex/tenant/cloud-id-123/wiki/api/v2/spaces?cursor=xyz"
        )

    def test_host_rooted_path_sharing_base_path_does_not_double_prefix(self) -> None:
        base_url = "https://example.com/api/v1"
        next_url = "/api/v1/items?page=2"
        assert (
            resolve_next_link_url(next_url, base_url)
            == "https://example.com/api/v1/items?page=2"
        )

    def test_path_boundary_prevents_false_prefix_match(self) -> None:
        base_url = "https://example.com/v"
        next_url = "/v2/items?page=2"
        assert (
            resolve_next_link_url(next_url, base_url)
            == "https://example.com/v/v2/items?page=2"
        )

    def test_relative_path_without_leading_slash(self) -> None:
        base_url = "https://api.example.com/tenant"
        next_url = "items?page=2"
        assert (
            resolve_next_link_url(next_url, base_url)
            == "https://api.example.com/tenant/items?page=2"
        )

    def test_query_only_next_link_keeps_current_path(self) -> None:
        base_url = "https://api.example.com/ex/tenant/cloud-id-123"
        current_url = (
            "https://api.example.com/ex/tenant/cloud-id-123/wiki/api/v2/spaces"
        )
        next_url = "?cursor=abc"
        assert (
            resolve_next_link_url(next_url, base_url, current_url=current_url)
            == "https://api.example.com/ex/tenant/cloud-id-123/wiki/api/v2/spaces?cursor=abc"
        )

    def test_query_only_next_link_falls_back_to_base_url_path(self) -> None:
        base_url = "https://api.example.com/ex/tenant/cloud-id-123"
        next_url = "?cursor=abc"
        assert (
            resolve_next_link_url(next_url, base_url)
            == "https://api.example.com/ex/tenant/cloud-id-123?cursor=abc"
        )

    def test_scheme_relative_next_link_inherits_base_scheme(self) -> None:
        base_url = "https://api.example.com/ex/tenant/cloud-id-123"
        next_url = "//cdn.example.com/wiki/api/v2/spaces?cursor=abc"
        assert (
            resolve_next_link_url(next_url, base_url)
            == "https://cdn.example.com/wiki/api/v2/spaces?cursor=abc"
        )
