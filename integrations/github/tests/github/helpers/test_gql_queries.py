from github.core.options import PullRequestGraphQLOptions
from github.helpers.gql_queries import (
    ALL_OPTIONAL_PR_FIELD_NAMES,
    generate_list_pull_requests_gql,
    generate_pr_fields,
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

    def test_includes_required_fields_by_default(self) -> None:
        query = generate_pull_request_details_gql(PullRequestGraphQLOptions())
        assert "fullDatabaseId" in query

    def test_can_omit_required_fields_for_single_field_fetch(self) -> None:
        # A backfill query for just `additions` selects that field and nothing else.
        options = PullRequestGraphQLOptions()
        fields = generate_pr_fields(
            options,
            extra_excluded_fields=[
                f for f in ALL_OPTIONAL_PR_FIELD_NAMES if f != "additions"
            ],
            include_required_fields=False,
        )
        assert fields.strip() == "additions"

    def test_pr_query_includes_change_metrics_by_default(self) -> None:
        options = PullRequestGraphQLOptions()
        query = generate_pull_request_details_gql(options)
        assert "additions" in query
        assert "deletions" in query
        assert "changedFiles" in query

    def test_can_exclude_change_metrics_fields(self) -> None:
        options = PullRequestGraphQLOptions(
            exclude_graphql_fields=["additions", "deletions", "changedFiles"]
        )
        query = generate_pull_request_details_gql(options)
        assert "additions" not in query
        assert "deletions" not in query
        assert "changedFiles" not in query

    def test_can_exclude_block_fields(self) -> None:
        options = PullRequestGraphQLOptions(
            exclude_graphql_fields=["author", "headRef"]
        )
        query = generate_pull_request_details_gql(options)
        # The top-level `author` block is excluded; the only remaining
        # `author {` is the one nested under the `reviews` block.
        assert query.count("author {") == 1
        assert "headRef {" not in query
