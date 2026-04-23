from github.core.options import PullRequestGraphQLOptions
from github.helpers.gql_queries import (
    PAGE_INFO_FRAGMENT,
    generate_list_pull_requests_gql,
    generate_pull_request_details_gql,
)


class TestGeneratePullRequestDetailsGql:
    def test_does_not_include_page_info_fragment(self) -> None:
        options = PullRequestGraphQLOptions()
        query = generate_pull_request_details_gql(options)
        assert "PageInfoFields" not in query

    def test_list_query_includes_page_info_fragment(self) -> None:
        options = PullRequestGraphQLOptions()
        query = generate_list_pull_requests_gql(options)
        assert "PageInfoFields" in query
