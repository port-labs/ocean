from integration import GithubPullRequestSelector


def test_pull_request_selector_accepts_exclude_graphql_fields_alias() -> None:
    selector = GithubPullRequestSelector.parse_obj(
        {
            "query": "true",
            "api": "graphql",
            "excludeGraphqlFields": ["additions", "author", "somethingElse"],
        }
    )

    assert selector.exclude_graphql_fields == ["additions", "author", "somethingElse"]
