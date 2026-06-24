from github.core.options import PullRequestGraphQLOptions
from github.helpers.gql_queries import (
    PR_NESTED_FIELDS_FETCHED_SEPARATELY,
    generate_list_pull_requests_gql,
    generate_pr_nested_fields_gql,
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


class TestEnrichNestedFieldsSeparately:
    def test_list_query_strips_nested_connections_when_enabled(self) -> None:
        options = PullRequestGraphQLOptions(enrich_nested_fields_separately=True)
        query = generate_list_pull_requests_gql(options)
        for nested in PR_NESTED_FIELDS_FETCHED_SEPARATELY:
            assert f"{nested}(" not in query and f"{nested} " not in query, nested

    def test_list_query_keeps_nested_connections_by_default(self) -> None:
        options = PullRequestGraphQLOptions()
        query = generate_list_pull_requests_gql(options)
        # Sanity-check: the default lean opt-out should still include the heavy
        # connections, so we know the strip is gated on the flag.
        assert "assignees(first: 10)" in query
        assert "reviews (first: 10)" in query

    def test_enrichment_query_contains_only_nested_connections(self) -> None:
        options = PullRequestGraphQLOptions(enrich_nested_fields_separately=True)
        query = generate_pr_nested_fields_gql(options)
        for nested in PR_NESTED_FIELDS_FETCHED_SEPARATELY:
            assert nested in query
        # Top-level PR scalars from the list query must not leak into the
        # enrichment query (review.createdAt nested inside `reviews` is OK).
        assert "additions" not in query
        assert "headRefName" not in query
        assert "mergeable" not in query
        assert "isDraft" not in query

    def test_enrichment_query_honors_exclude_graphql_fields(self) -> None:
        # Even when enriching separately, the user's `exclude_graphql_fields` is
        # still respected — letting a customer skip e.g. `reviews` entirely.
        options = PullRequestGraphQLOptions(
            enrich_nested_fields_separately=True,
            exclude_graphql_fields=["reviews"],
        )
        query = generate_pr_nested_fields_gql(options)
        assert "reviews(" not in query
        assert "assignees(" in query
