import pytest
from unittest.mock import patch
from httpx import HTTPStatusError, Request, Response
from typing import Any, AsyncGenerator, Dict, List, Optional

from bitbucket_cloud.helpers.exceptions import BitbucketFileWalkError
from bitbucket_cloud.helpers.file_kind import (
    MAX_FILE_SIZE,
    MAX_LISTING_DEPTH,
    REPOSITORY_EXPANSION,
    build_listing_root,
    build_source_filter,
    escape_bbql_string,
    process_file_patterns,
    repository_matches,
    select_matching_files,
    validate_file_match,
)
from integration import BitbucketFilePattern


def repo(
    slug: str, name: Optional[str] = None, size: int = 2048, branch: str = "main"
) -> Dict[str, Any]:
    return {
        "slug": slug,
        "name": name if name is not None else slug,
        "size": size,
        "mainbranch": {"name": branch},
    }


def entry(path: str, size: int = 24) -> Dict[str, Any]:
    return {
        "path": path,
        "type": "commit_file",
        "size": size,
        "commit": {
            "repository": {"name": "display name", "mainbranch": {"name": "main"}}
        },
    }


def http_error(status: int) -> HTTPStatusError:
    response = Response(status, request=Request("GET", "https://example/src"))
    return HTTPStatusError(f"{status}", request=response.request, response=response)


class FakeClient:
    """Stands in for BitbucketClient, recording what the walk asked it for."""

    def __init__(
        self,
        repositories: List[Dict[str, Any]],
        listings: Dict[str, Any],
        contents: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.repositories = repositories
        self.listings = listings
        self.contents = contents or {}
        self.repository_params: Any = "not called"
        self.listing_calls: List[Dict[str, Any]] = []
        self.content_calls: List[tuple[str, str, str]] = []

    async def get_repositories(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        self.repository_params = params
        yield self.repositories

    async def get_directory_contents(
        self,
        repo_slug: str,
        branch: str,
        path: str,
        max_depth: int,
        params: Optional[Dict[str, Any]] = None,
        raise_on_missing: bool = False,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        self.listing_calls.append(
            {
                "repo": repo_slug,
                "branch": branch,
                "root": path,
                "max_depth": max_depth,
                "params": params,
                "raise_on_missing": raise_on_missing,
            }
        )
        listing = self.listings.get(repo_slug, [])
        if isinstance(listing, Exception):
            raise listing
        yield listing

    async def get_repository_files(
        self, repo_slug: str, branch: str, path: str
    ) -> Optional[str]:
        self.content_calls.append((repo_slug, branch, path))
        content = self.contents.get(path, f"content of {path}")
        if isinstance(content, Exception):
            raise content
        return content


async def walk(
    client: FakeClient, **pattern: Any
) -> tuple[List[Dict[str, Any]], Optional[BaseException]]:
    """Run the walk to completion, returning what it emitted and what it raised."""
    pattern.setdefault("path", "/")
    pattern.setdefault("skipParsing", True)
    emitted: List[Dict[str, Any]] = []
    raised: Optional[BaseException] = None
    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        try:
            async for batch in process_file_patterns(BitbucketFilePattern(**pattern)):
                emitted.extend(batch)
        except (
            BaseException
        ) as error:  # noqa: B036 - the walk's verdict is the assertion
            raised = error
    return emitted, raised


def test_escape_bbql_string() -> None:
    """A backslash and a quote both need escaping, and in that order."""
    assert escape_bbql_string("README") == "README"
    assert escape_bbql_string('RE"ADME') == 'RE\\"ADME'
    assert escape_bbql_string("a\\b") == "a\\\\b"
    assert escape_bbql_string('a\\"b') == 'a\\\\\\"b'


def test_build_source_filter_covers_every_filename_in_one_query() -> None:
    """One disjunction per repository, not one request per filename."""
    assert (
        build_source_filter(["port.yml", "README.md"])
        == 'type="commit_file" AND (path~"port.yml" OR path~"README.md")'
    )
    assert build_source_filter(['a"b']) == 'type="commit_file" AND (path~"a\\"b")'


@pytest.mark.parametrize("path", ["*/", "*", "**/*", "**", "", "/"])
def test_build_listing_root_is_empty_for_every_global_path(path: str) -> None:
    """The default configuration lists from the repository root."""
    assert build_listing_root(path) == ""


@pytest.mark.parametrize(
    ("path", "root"),
    [("charts/*", "charts"), ("a/b/*/c", "a/b"), ("charts", "charts")],
)
def test_build_listing_root_keeps_the_literal_prefix(path: str, root: str) -> None:
    assert build_listing_root(path) == root


@pytest.mark.parametrize(
    "configured", ["my-repo", "My Repo", "My-Repo", "MY-REPO", "my repo"]
)
def test_repository_matches_accepts_slug_display_name_and_hyphenated(
    configured: str,
) -> None:
    assert repository_matches(repo("my-repo", name="My Repo"), {configured.lower()})


def test_repository_matches_rejects_another_repository() -> None:
    assert not repository_matches(repo("my-repo", name="My Repo"), {"other-repo"})


def test_select_matching_files_narrows_what_the_server_filter_returned() -> None:
    """Tested without a client, the way folder.py's find_matching_folders is."""
    pattern = BitbucketFilePattern(path="*/", filenames=["font-awesome.css"])
    page = [entry("css/font-awesome.css"), entry("css/font-awesome.css.map")]

    assert [e["path"] for e in select_matching_files(page, pattern, "repo-one")] == [
        "css/font-awesome.css"
    ]


def test_select_matching_files_drops_an_oversized_entry() -> None:
    pattern = BitbucketFilePattern(path="*/", filenames=["big.yml", "small.yml"])
    page = [entry("big.yml", size=MAX_FILE_SIZE + 1), entry("small.yml")]

    assert [e["path"] for e in select_matching_files(page, pattern, "repo-one")] == [
        "small.yml"
    ]


@pytest.mark.asyncio
async def test_the_walk_lists_each_repository_once_with_the_filter() -> None:
    client = FakeClient(
        [repo("repo-one"), repo("repo-two")],
        {"repo-one": [entry("port.yml")], "repo-two": [entry("port.yml")]},
    )
    emitted, raised = await walk(client, filenames=["port.yml"])

    assert raised is None
    assert [item["metadata"]["path"] for item in emitted] == ["port.yml", "port.yml"]
    assert [call["repo"] for call in client.listing_calls] == ["repo-one", "repo-two"]
    assert client.listing_calls[0]["params"] == {
        "q": 'type="commit_file" AND (path~"port.yml")',
        "fields": REPOSITORY_EXPANSION,
    }
    assert client.listing_calls[0]["max_depth"] == MAX_LISTING_DEPTH
    assert client.listing_calls[0]["branch"] == "main"


@pytest.mark.asyncio
async def test_the_walk_shares_the_repository_listing_cache_key() -> None:
    """An empty dict is what the other kinds pass when no selector is configured."""
    client = FakeClient([repo("repo-one")], {"repo-one": []})
    await walk(client, filenames=["port.yml"])
    assert client.repository_params == {}


@pytest.mark.asyncio
async def test_a_repository_with_no_commits_is_skipped_before_any_request() -> None:
    """Its listing would answer 404 Commit not found, which is the raise path."""
    client = FakeClient([repo("empty-repo", size=0)], {})
    emitted, raised = await walk(client, filenames=["port.yml"])

    assert emitted == []
    assert raised is None
    assert client.listing_calls == []


@pytest.mark.asyncio
async def test_the_repos_selector_narrows_which_repositories_are_walked() -> None:
    client = FakeClient(
        [repo("repo-one"), repo("repo-two")],
        {"repo-one": [entry("port.yml")], "repo-two": [entry("port.yml")]},
    )
    emitted, raised = await walk(client, filenames=["port.yml"], repos=["repo-two"])

    assert raised is None
    assert [call["repo"] for call in client.listing_calls] == ["repo-two"]
    assert len(emitted) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("path", "root"), [("*/", ""), ("charts/*", "charts")])
async def test_the_listing_root_is_derived_and_every_error_is_the_clients_to_judge(
    path: str, root: str
) -> None:
    """Which 404s are tolerated follows from the root, and is decided in the client.

    See test_client.py: raise_on_missing tolerates an absent path only when one was
    asked for, so an empty root tolerates nothing without the walk saying so.
    """
    client = FakeClient([repo("repo-one")], {"repo-one": []})
    await walk(client, filenames=["port.yml"], path=path)
    assert client.listing_calls[0]["root"] == root
    assert client.listing_calls[0]["raise_on_missing"] is True


@pytest.mark.asyncio
async def test_an_entry_the_filter_returns_and_the_matcher_rejects_is_not_emitted() -> (
    None
):
    """path~ is a substring match, so the server returns more than the matcher accepts."""
    client = FakeClient(
        [repo("repo-one")],
        {
            "repo-one": [
                entry("css/font-awesome.css.map"),
                entry("css/font-awesome.css"),
            ]
        },
    )
    emitted, raised = await walk(client, filenames=["font-awesome.css"], path="*/")

    assert raised is None
    assert [item["metadata"]["path"] for item in emitted] == ["css/font-awesome.css"]
    assert [call[2] for call in client.content_calls] == ["css/font-awesome.css"]


@pytest.mark.asyncio
async def test_a_dotfile_is_discovered_and_emitted() -> None:
    client = FakeClient([repo("repo-one")], {"repo-one": [entry(".nvmrc")]})
    emitted, raised = await walk(client, filenames=[".nvmrc"])

    assert raised is None
    assert [item["metadata"]["path"] for item in emitted] == [".nvmrc"]


@pytest.mark.asyncio
async def test_an_oversized_file_is_skipped_without_fetching_it() -> None:
    client = FakeClient(
        [repo("repo-one")],
        {"repo-one": [entry("big.yml", size=MAX_FILE_SIZE + 1), entry("small.yml")]},
    )
    emitted, raised = await walk(client, filenames=["big.yml", "small.yml"])

    assert raised is None
    assert [item["metadata"]["path"] for item in emitted] == ["small.yml"]
    assert [call[2] for call in client.content_calls] == ["small.yml"]


@pytest.mark.asyncio
async def test_the_emitted_object_carries_the_listing_repository_and_the_entry() -> (
    None
):
    listed = repo("repo-one", name="Display Name")
    client = FakeClient([listed], {"repo-one": [entry("port.yml")]})
    emitted, raised = await walk(client, filenames=["port.yml"])

    assert raised is None
    assert set(emitted[0]) == {"content", "branch", "repo", "metadata"}
    assert emitted[0]["repo"] is listed
    assert emitted[0]["branch"] == "main"
    assert emitted[0]["metadata"]["path"] == "port.yml"
    assert emitted[0]["content"] == "content of port.yml"


@pytest.mark.asyncio
async def test_one_unreadable_file_costs_its_repository_and_not_the_others() -> None:
    """Collection is per repository, as it is in the github file exporter."""
    client = FakeClient(
        [repo("repo-one"), repo("repo-two")],
        {"repo-one": [entry("a.yml")], "repo-two": [entry("b.yml")]},
        {"a.yml": None},
    )
    emitted, raised = await walk(client, filenames=["a.yml", "b.yml"])

    assert [item["metadata"]["path"] for item in emitted] == ["b.yml"]
    assert isinstance(raised, BitbucketFileWalkError)
    assert "1 repository could not be walked" in str(raised)


@pytest.mark.asyncio
async def test_one_unreadable_repository_keeps_the_others() -> None:
    client = FakeClient(
        [repo("broken"), repo("repo-two")],
        {"broken": http_error(403), "repo-two": [entry("port.yml")]},
    )
    emitted, raised = await walk(client, filenames=["port.yml"])

    assert [item["metadata"]["path"] for item in emitted] == ["port.yml"]
    assert isinstance(raised, BitbucketFileWalkError)
    cause = raised.__cause__
    assert isinstance(cause, ExceptionGroup)
    assert isinstance(cause.exceptions[0], HTTPStatusError)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [403, 500])
async def test_a_failed_listing_is_collected_whatever_its_status(status: int) -> None:
    """Every status but the two that end the walk is the one repository's own problem.

    401 and 429 are covered by test_a_dead_credential_or_exhausted_quota_stops_the_walk.
    """
    client = FakeClient(
        [repo("broken"), repo("repo-two")],
        {"broken": http_error(status), "repo-two": [entry("port.yml")]},
    )
    emitted, raised = await walk(client, filenames=["port.yml"])

    assert [item["metadata"]["path"] for item in emitted] == ["port.yml"]
    assert isinstance(raised, BitbucketFileWalkError)


@pytest.mark.asyncio
async def test_no_filenames_configured_makes_no_requests() -> None:
    client = FakeClient([repo("repo-one")], {})
    emitted, raised = await walk(client, filenames=[])

    assert emitted == []
    assert raised is None
    assert client.repository_params == "not called"


def test_validate_file_match() -> None:
    """Test validate_file_match function."""
    assert validate_file_match("src/main/test.py", "test.py", "src/main")
    assert validate_file_match("test.py", "test.py", "")
    assert validate_file_match("test.py", "test.py", "/")
    assert validate_file_match(".nvmrc", ".nvmrc", "/")
    assert validate_file_match("src/.gitignore", ".gitignore", "src")
    assert validate_file_match(".env", ".env", "")
    assert not validate_file_match("src/main/other.py", "test.py", "src/main")
    assert not validate_file_match("src/test/test.py", "test.py", "src/main")


@pytest.mark.parametrize(
    "expected_path",
    ["hello/test", "/hello/test", "/hello/test/", "hello/test/"],
)
def test_validate_file_match_ignores_path_slash_variants(expected_path: str) -> None:
    """Leading/trailing slashes on the configured path must not change matching."""
    assert validate_file_match("hello/test/file.txt", "file.txt", expected_path)
    assert not validate_file_match("hello/other/file.txt", "file.txt", expected_path)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 429])
async def test_a_dead_credential_or_exhausted_quota_stops_the_walk(status: int) -> None:
    """Neither status is about one repository, so the rest are not attempted.

    Carried forward from the search-based walk, where it shipped in the client fixes.
    A rotated-out token or an exhausted hourly window can both arrive after
    get_repositories has already succeeded, and recording one per repository would
    mean a few hundred more doomed requests.
    """
    client = FakeClient(
        [repo("broken"), repo("repo-two")],
        {"broken": http_error(status), "repo-two": [entry("port.yml")]},
    )
    emitted, raised = await walk(client, filenames=["port.yml"])

    assert emitted == []
    assert isinstance(raised, HTTPStatusError)
    assert [call["repo"] for call in client.listing_calls] == ["broken"]


@pytest.mark.asyncio
async def test_a_renamed_repository_is_addressed_by_its_real_slug() -> None:
    """The content fetch addresses the slug, never the display name.

    ``entry()`` carries only a display name on its embedded repository object, so a
    walk that read the slug back out of the entry would request "display name" here.
    """
    client = FakeClient(
        [repo("payments-api", name="Billing Service")],
        {"payments-api": [entry("port.yml")]},
    )
    emitted, raised = await walk(client, filenames=["port.yml"])

    assert raised is None
    assert client.content_calls == [("payments-api", "main", "port.yml")]
    assert [item["metadata"]["path"] for item in emitted] == ["port.yml"]
