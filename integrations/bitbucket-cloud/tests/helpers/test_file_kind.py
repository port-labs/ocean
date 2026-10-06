import asyncio
import pytest
from loguru import logger
from httpx import HTTPStatusError, Request, Response
from unittest.mock import patch
from bitbucket_cloud.helpers.file_kind import (
    FILE_BATCH_SIZE,
    MAX_CONCURRENT_FILE_FETCHES,
    MAX_FILE_SIZE,
    MAX_LISTING_DEPTH,
    build_file_filter,
    build_listing_root,
    escape_bbql_string,
    has_main_branch,
    process_file_patterns,
    repository_matches,
)
from bitbucket_cloud.helpers.utils import filename_matches, validate_file_match
from integration import BitbucketFilePattern
from port_ocean.exceptions.core import OceanAbortException
from typing import Any, AsyncGenerator, Dict, Iterator, List, Mapping, Optional


def repository(
    slug: str, name: Optional[str] = None, mainbranch: Optional[str] = "main"
) -> Dict[str, Any]:
    return {
        "slug": slug,
        "name": name or slug,
        "full_name": f"test-workspace/{slug}",
        "mainbranch": {"name": mainbranch} if mainbranch else None,
    }


def listing_entry(path: str, commit_hash: str = "deadbeef") -> Dict[str, Any]:
    return {
        "path": path,
        "type": "commit_file",
        "size": 12,
        "commit": {"hash": commit_hash, "type": "commit"},
    }


class FakeClient:
    """Stands in for BitbucketClient with the real signatures, recording every call."""

    def __init__(
        self,
        repositories: List[Dict[str, Any]],
        listings: Dict[str, List[List[Dict[str, Any]]]],
        contents: Optional[Mapping[str, Optional[str]]] = None,
        listing_errors: Optional[Dict[str, Exception]] = None,
        errors_by_path: Optional[Dict[str, Exception]] = None,
        repository_batches: Optional[List[List[Dict[str, Any]]]] = None,
    ) -> None:
        self._repository_batches = repository_batches or [repositories]
        self._listings = listings
        self._contents: Mapping[str, Optional[str]] = contents or {}
        self._listing_errors = listing_errors or {}
        self._errors_by_path = errors_by_path or {}
        self.repository_calls: List[Optional[Dict[str, Any]]] = []
        self.listing_calls: List[Dict[str, Any]] = []
        self.content_calls: List[tuple[str, str, str]] = []
        self.in_flight_content = 0
        self.max_in_flight_content = 0

    async def get_repositories(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        self.repository_calls.append(params)
        for batch in self._repository_batches:
            yield batch

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
                "repo_slug": repo_slug,
                "branch": branch,
                "path": path,
                "max_depth": max_depth,
                "params": params,
                "raise_on_missing": raise_on_missing,
            }
        )
        if path in self._errors_by_path:
            # Mirror the real client: a 404 only surfaces when the caller asked for it,
            # otherwise _send_api_request turns it into an empty result.
            if raise_on_missing:
                raise self._errors_by_path[path]
            return
        if repo_slug in self._listing_errors:
            raise self._listing_errors[repo_slug]
        for batch in self._listings.get(repo_slug, []):
            yield batch

    async def get_repository_files(
        self, repo: str, branch: str, path: str
    ) -> Optional[str]:
        self.content_calls.append((repo, branch, path))
        self.in_flight_content += 1
        self.max_in_flight_content = max(
            self.max_in_flight_content, self.in_flight_content
        )
        try:
            await asyncio.sleep(0.01)
            return self._contents.get(path, "file content")
        finally:
            self.in_flight_content -= 1

    @property
    def listed_slugs(self) -> List[str]:
        return [call["repo_slug"] for call in self.listing_calls]


async def discover(
    client: FakeClient,
    file_pattern: BitbucketFilePattern,
    repository_params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        results: List[Dict[str, Any]] = []
        async for batch in process_file_patterns(file_pattern, repository_params or {}):
            results.extend(batch)
        return results


async def discover_batches(
    client: FakeClient, file_pattern: BitbucketFilePattern
) -> List[List[Dict[str, Any]]]:
    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        return [batch async for batch in process_file_patterns(file_pattern, {})]


def test_build_file_filter_single_filename() -> None:
    assert build_file_filter(["port.yml"]) == 'type="commit_file" AND (path~"port.yml")'


def test_build_file_filter_multiple_filenames_use_one_query() -> None:
    assert build_file_filter(["port.yml", "README.md"]) == (
        'type="commit_file" AND (path~"port.yml" OR path~"README.md")'
    )


def test_build_file_filter_keeps_dotfiles_intact() -> None:
    assert build_file_filter([".nvmrc"]) == 'type="commit_file" AND (path~".nvmrc")'


@pytest.mark.parametrize(
    "path,expected",
    [
        ("*/", ""),
        ("*", ""),
        ("**", ""),
        ("**/*", ""),
        ("", ""),
        ("/", ""),
        ("src", "src"),
        ("/src/", "src"),
        ("src/*", "src"),
        ("a/b/**/c", "a/b"),
    ],
)
def test_build_listing_root(path: str, expected: str) -> None:
    assert build_listing_root(path) == expected


@pytest.mark.parametrize(
    "configured,expected",
    [
        ([], True),
        (["my-repo"], True),
        (["My Repo"], True),
        (["My-Repo"], True),
        (["MY-REPO"], True),
        (["other"], False),
    ],
)
def test_repository_matches(configured: List[str], expected: bool) -> None:
    repo = repository("my-repo", name="My Repo")
    assert repository_matches(repo, configured) is expected


@pytest.mark.parametrize(
    "repo,expected",
    [
        (repository("healthy"), True),
        (repository("empty", mainbranch=None), False),
        (repository("blank", mainbranch=""), False),
        ({"slug": "no-key", "name": "no-key"}, False),
    ],
)
def test_has_main_branch(repo: Dict[str, Any], expected: bool) -> None:
    assert has_main_branch(repo) is expected


def test_validate_file_match() -> None:
    assert validate_file_match("src/test.py", "test.py", "src")
    assert not validate_file_match("src/test.py", "test.py", "other")
    assert validate_file_match("test.py", "test.py", "/")
    assert not validate_file_match("src/other.py", "test.py", "src")


@pytest.mark.parametrize("expected_path", ["src", "/src", "src/", "/src/"])
def test_validate_file_match_ignores_path_slash_variants(expected_path: str) -> None:
    assert validate_file_match("src/test.py", "test.py", expected_path)


@pytest.mark.asyncio
async def test_no_filenames_makes_no_api_calls() -> None:
    client = FakeClient(repositories=[repository("repo")], listings={})

    results = await discover(
        client, BitbucketFilePattern(path="src", filenames=[], skipParsing=False)
    )

    assert results == []
    assert client.repository_calls == []
    assert client.listing_calls == []


@pytest.mark.asyncio
async def test_lists_each_repository_with_filter_and_full_depth() -> None:
    client = FakeClient(
        repositories=[repository("repo")],
        listings={"repo": [[listing_entry("README.md")]]},
    )

    results = await discover(
        client,
        BitbucketFilePattern(path="/", filenames=["README.md"], skipParsing=False),
    )

    assert len(results) == 1
    assert client.repository_calls == [{}]
    assert len(client.listing_calls) == 1
    call = client.listing_calls[0]
    assert call["repo_slug"] == "repo"
    assert call["branch"] == "main"
    assert call["path"] == ""
    assert call["max_depth"] == MAX_LISTING_DEPTH
    assert call["params"]["q"] == 'type="commit_file" AND (path~"README.md")'
    assert call["params"]["fields"] == "+values.commit.repository.mainbranch.name"


@pytest.mark.asyncio
async def test_filters_repositories_by_configured_names() -> None:
    client = FakeClient(
        repositories=[
            repository("wanted-slug"),
            repository("wanted-name", name="Wanted Name"),
            repository("unwanted"),
        ],
        listings={
            "wanted-slug": [[listing_entry("README.md")]],
            "wanted-name": [[listing_entry("README.md")]],
            "unwanted": [[listing_entry("README.md")]],
        },
    )

    results = await discover(
        client,
        BitbucketFilePattern(
            path="/",
            repos=["wanted-slug", "Wanted-Name"],
            filenames=["README.md"],
            skipParsing=False,
        ),
    )

    assert sorted(client.listed_slugs) == ["wanted-name", "wanted-slug"]
    assert len(results) == 2


@pytest.mark.asyncio
async def test_skips_repository_without_mainbranch_and_keeps_the_rest() -> None:
    client = FakeClient(
        repositories=[repository("empty", mainbranch=None), repository("healthy")],
        listings={"healthy": [[listing_entry("README.md")]]},
    )

    results = await discover(
        client,
        BitbucketFilePattern(path="/", filenames=["README.md"], skipParsing=False),
    )

    assert client.listed_slugs == ["healthy"]
    assert len(results) == 1


@pytest.mark.asyncio
async def test_rejects_contains_matches_outside_the_configured_path() -> None:
    """path~ is a contains match, so validate_file_match must still narrow the result."""
    client = FakeClient(
        repositories=[repository("repo")],
        listings={
            "repo": [[listing_entry("src/test.py"), listing_entry("other/test.py")]]
        },
    )

    results = await discover(
        client,
        BitbucketFilePattern(path="src", filenames=["test.py"], skipParsing=False),
    )

    assert [result["metadata"]["path"] for result in results] == ["src/test.py"]


@pytest.mark.asyncio
async def test_discovers_nested_files() -> None:
    """Pins full recursion: a future max_depth narrowing would drop the nested file."""
    client = FakeClient(
        repositories=[repository("repo")],
        listings={
            "repo": [[listing_entry("README.md"), listing_entry("a/b/c/README.md")]]
        },
    )

    results = await discover(
        client,
        BitbucketFilePattern(path="*/", filenames=["README.md"], skipParsing=False),
    )

    assert sorted(result["metadata"]["path"] for result in results) == [
        "README.md",
        "a/b/c/README.md",
    ]


@pytest.mark.asyncio
async def test_fetches_by_repository_slug_not_display_name() -> None:
    client = FakeClient(
        repositories=[
            repository(
                "confluence-support-fix-missing-attachments",
                name="Confluence Support - Fix Missing Attachments",
            )
        ],
        listings={
            "confluence-support-fix-missing-attachments": [[listing_entry("README.md")]]
        },
    )

    await discover(
        client,
        BitbucketFilePattern(path="/", filenames=["README.md"], skipParsing=False),
    )

    assert client.listed_slugs == ["confluence-support-fix-missing-attachments"]
    assert client.content_calls == [
        ("confluence-support-fix-missing-attachments", "deadbeef", "README.md")
    ]


@pytest.mark.asyncio
async def test_fetches_content_at_the_listed_commit_hash() -> None:
    """Fetching by immutable ref removes the listing-to-content race."""
    client = FakeClient(
        repositories=[repository("repo")],
        listings={"repo": [[listing_entry("README.md", commit_hash="abc1234")]]},
    )

    await discover(
        client,
        BitbucketFilePattern(path="/", filenames=["README.md"], skipParsing=False),
    )

    assert client.content_calls == [("repo", "abc1234", "README.md")]


@pytest.mark.asyncio
async def test_ingests_dotfiles() -> None:
    """Dotfiles have no extension to filter on; they must still be discovered."""
    filenames = [".nvmrc", ".gitignore", ".env"]
    contents = {
        ".nvmrc": "18",
        ".gitignore": "node_modules/\n.env\n",
        ".env": "SECRET=value\n",
    }
    client = FakeClient(
        repositories=[repository("repo")],
        listings={"repo": [[listing_entry(filename) for filename in filenames]]},
        contents=contents,
    )

    results = await discover(
        client,
        BitbucketFilePattern(path="/", filenames=filenames, skipParsing=False),
    )

    assert sorted(result["metadata"]["path"] for result in results) == sorted(filenames)
    assert {result["metadata"]["path"]: result["content"] for result in results} == (
        contents
    )


@pytest.mark.asyncio
async def test_emitted_object_has_no_top_level_path_key() -> None:
    """No top-level `path` key: includedFiles resolves from the repository root."""
    client = FakeClient(
        repositories=[repository("repo")],
        listings={"repo": [[listing_entry("README.md")]]},
    )

    results = await discover(
        client,
        BitbucketFilePattern(path="/", filenames=["README.md"], skipParsing=False),
    )

    assert set(results[0]) == {"content", "metadata", "repo", "branch"}
    assert results[0]["branch"] == "main"
    assert results[0]["repo"]["slug"] == "repo"


@pytest.mark.asyncio
async def test_keeps_repository_metadata_leaves_from_the_listing() -> None:
    entry = listing_entry("README.md")
    entry["commit"]["repository"] = {"name": "Repo", "full_name": "ws/repo"}
    client = FakeClient(repositories=[repository("repo")], listings={"repo": [[entry]]})

    results = await discover(
        client,
        BitbucketFilePattern(path="/", filenames=["README.md"], skipParsing=False),
    )

    assert results[0]["metadata"]["commit"]["repository"]["full_name"] == "ws/repo"


@pytest.mark.asyncio
async def test_listing_failure_aborts_after_healthy_repositories_yield() -> None:
    """Both halves matter: a fail-fast merge would lose the healthy repository's file."""
    failure = Exception("403 Forbidden")
    client = FakeClient(
        repositories=[repository("broken"), repository("healthy")],
        listings={"healthy": [[listing_entry("README.md")]]},
        listing_errors={"broken": failure},
    )

    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        results: List[Dict[str, Any]] = []
        with pytest.raises(OceanAbortException) as abort:
            async for batch in process_file_patterns(
                BitbucketFilePattern(
                    path="/", filenames=["README.md"], skipParsing=False
                ),
                {},
            ):
                results.extend(batch)

    assert [result["metadata"]["path"] for result in results] == ["README.md"]
    # every failure is preserved, not just the first
    cause = abort.value.__cause__
    assert isinstance(cause, ExceptionGroup)  # noqa: F821
    assert list(cause.exceptions) == [failure]


@pytest.mark.asyncio
async def test_skips_files_above_the_size_limit() -> None:
    """Code search never indexed files this large, so a tree listing must not ingest them."""
    small = listing_entry("README.md")
    large = listing_entry("big/README.md")
    large["size"] = MAX_FILE_SIZE + 1
    client = FakeClient(
        repositories=[repository("repo")], listings={"repo": [[small, large]]}
    )

    results = await discover(
        client,
        BitbucketFilePattern(path="*/", filenames=["README.md"], skipParsing=False),
    )

    assert [result["metadata"]["path"] for result in results] == ["README.md"]
    assert client.content_calls == [("repo", "deadbeef", "README.md")]


@pytest.mark.asyncio
async def test_keeps_files_at_the_size_limit() -> None:
    entry = listing_entry("README.md")
    entry["size"] = MAX_FILE_SIZE
    client = FakeClient(repositories=[repository("repo")], listings={"repo": [[entry]]})

    results = await discover(
        client,
        BitbucketFilePattern(path="/", filenames=["README.md"], skipParsing=False),
    )

    assert len(results) == 1


@pytest.mark.asyncio
async def test_failure_in_one_batch_does_not_stop_later_batches() -> None:
    """Repository pages are merged per batch, so failures must be carried across them."""
    failure = Exception("403 Forbidden")
    client = FakeClient(
        repositories=[],
        repository_batches=[
            [repository("broken"), repository("first")],
            [repository("second")],
        ],
        listings={
            "first": [[listing_entry("first/README.md")]],
            "second": [[listing_entry("second/README.md")]],
        },
        listing_errors={"broken": failure},
    )

    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        results: List[Dict[str, Any]] = []
        with pytest.raises(OceanAbortException) as abort:
            async for batch in process_file_patterns(
                BitbucketFilePattern(
                    path="*/", filenames=["README.md"], skipParsing=False
                ),
                {},
            ):
                results.extend(batch)

    assert sorted(result["metadata"]["path"] for result in results) == [
        "first/README.md",
        "second/README.md",
    ]
    assert "1 of 3 repositories" in str(abort.value)
    # every failure is preserved, not just the first
    cause = abort.value.__cause__
    assert isinstance(cause, ExceptionGroup)  # noqa: F821
    assert list(cause.exceptions) == [failure]


@pytest.mark.asyncio
async def test_repository_filter_reaches_the_repositories_call() -> None:
    """The file kind walks repositories, so the parent filter has to narrow the walk."""
    client = FakeClient(
        repositories=[repository("repo-a")],
        listings={"repo-a": [[listing_entry("port.yml")]]},
    )

    await discover(
        client,
        BitbucketFilePattern(filenames=["port.yml"]),
        repository_params={"role": "member", "q": 'name="repo-a"'},
    )

    assert client.repository_calls == [{"role": "member", "q": 'name="repo-a"'}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path, listed, raises_on_404",
    [
        # Nothing can be legitimately missing at the root, so a 404 must not pass as
        # empty - that is what let reconciliation delete the kind's entities.
        ("*/", "port.yml", True),
        ("/", "port.yml", True),
        # A configured directory may genuinely not exist, which is the common case.
        ("charts/*", "charts/app/port.yml", False),
    ],
)
async def test_only_a_root_listing_404_is_a_failure(
    path: str, listed: str, raises_on_404: bool
) -> None:
    client = FakeClient(
        repositories=[repository("repo-a")],
        listings={"repo-a": [[listing_entry(listed)]]},
    )

    await discover(client, BitbucketFilePattern(path=path, filenames=["port.yml"]))

    assert [call["raise_on_missing"] for call in client.listing_calls] == [
        raises_on_404
    ]


@pytest.mark.asyncio
async def test_files_are_emitted_in_batches() -> None:
    """One entity per batch means one transform and one upsert round trip per file."""
    entries = [listing_entry(f"dir{index}/port.yml") for index in range(5)]
    client = FakeClient(
        repositories=[repository("repo-a")],
        listings={"repo-a": [entries]},
    )

    batches = await discover_batches(
        client, BitbucketFilePattern(path="*", filenames=["port.yml"])
    )

    assert [len(batch) for batch in batches] == [5]
    assert all(len(batch) <= FILE_BATCH_SIZE for batch in batches)


@pytest.mark.asyncio
async def test_content_fetches_are_bounded_across_repositories() -> None:
    """The repository bound alone still allows repos x page-size concurrent fetches."""
    repositories = [repository(f"repo-{index}") for index in range(5)]
    listings = {
        repo["slug"]: [[listing_entry(f"dir{index}/port.yml") for index in range(20)]]
        for repo in repositories
    }
    client = FakeClient(repositories=repositories, listings=listings)

    results = await discover(
        client, BitbucketFilePattern(path="*", filenames=["port.yml"])
    )

    assert len(results) == 100
    assert client.max_in_flight_content <= MAX_CONCURRENT_FILE_FETCHES


@pytest.fixture
def warning_messages() -> Iterator[List[str]]:
    """Collect WARNING-level loguru records.

    loguru does not propagate to pytest's caplog, so a caplog assertion would pass
    whether or not the message was emitted.
    """
    messages: List[str] = []
    sink_id = logger.add(lambda record: messages.append(str(record)), level="WARNING")
    try:
        yield messages
    finally:
        logger.remove(sink_id)


@pytest.mark.asyncio
async def test_no_workspace_wide_warning_when_a_filter_narrows_the_walk(
    warning_messages: List[str],
) -> None:
    """The warning claims the whole workspace is walked; repoQuery means it is not."""
    client = FakeClient(
        repositories=[repository("repo-a")],
        listings={"repo-a": [[listing_entry("port.yml")]]},
    )

    await discover(
        client,
        BitbucketFilePattern(filenames=["port.yml"]),
        repository_params={"q": 'name~"repo"'},
    )

    assert not any("across the workspace" in m for m in warning_messages)


@pytest.mark.asyncio
async def test_warns_when_nothing_narrows_the_walk(
    warning_messages: List[str],
) -> None:
    client = FakeClient(
        repositories=[repository("repo-a")],
        listings={"repo-a": [[listing_entry("port.yml")]]},
    )

    await discover(client, BitbucketFilePattern(filenames=["port.yml"]))

    assert any("across the workspace" in m for m in warning_messages)


def not_found() -> HTTPStatusError:
    request = Request("GET", "https://api.bitbucket.org/2.0/x")
    return HTTPStatusError(
        "404", request=request, response=Response(404, request=request)
    )


@pytest.mark.asyncio
async def test_absent_configured_path_is_not_a_failure() -> None:
    """A repository with no such directory must not abort - its root reads fine."""
    client = FakeClient(
        repositories=[repository("repo-a")],
        listings={"repo-a": [[]]},
        errors_by_path={"charts": not_found()},
    )

    results = await discover(
        client, BitbucketFilePattern(path="charts/*", filenames=["port.yml"])
    )

    assert results == []
    assert [call["path"] for call in client.listing_calls] == ["charts"]


@pytest.mark.asyncio
async def test_lost_access_to_one_repository_with_a_sub_path_is_not_detected() -> None:
    """The accepted gap. Bitbucket answers 404 for no-permission as well as for an
    absent directory, so with a sub-path configured the two are indistinguishable and
    this repository's file entities can be deleted. Separating them costs one request
    for every repository that does not have the path, which is most of them."""
    client = FakeClient(
        repositories=[repository("repo-a")],
        listings={},
        errors_by_path={"charts": not_found()},
    )

    results = await discover(
        client, BitbucketFilePattern(path="charts/*", filenames=["port.yml"])
    )

    assert results == []
    assert [call["path"] for call in client.listing_calls] == ["charts"]


@pytest.mark.asyncio
async def test_root_listing_404_is_a_failure() -> None:
    """With no configured sub-path, nothing could legitimately be absent."""
    client = FakeClient(
        repositories=[repository("repo-a")],
        listings={},
        errors_by_path={"": not_found()},
    )

    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        with pytest.raises(OceanAbortException):
            async for _ in process_file_patterns(
                BitbucketFilePattern(filenames=["port.yml"]), {}
            ):
                pass

    assert [call["path"] for call in client.listing_calls] == [""]


def status_error(status_code: int) -> HTTPStatusError:
    request = Request("GET", "https://api.bitbucket.org/2.0/x")
    return HTTPStatusError(
        str(status_code),
        request=request,
        response=Response(status_code, request=request),
    )


@pytest.fixture
def error_messages() -> Iterator[List[str]]:
    """Collect ERROR-level loguru records, for the same reason as warning_messages."""
    messages: List[str] = []
    sink_id = logger.add(lambda record: messages.append(str(record)), level="ERROR")
    try:
        yield messages
    finally:
        logger.remove(sink_id)


@pytest.mark.asyncio
async def test_failure_log_names_the_repository(
    error_messages: List[str],
) -> None:
    """The framework logs "iterator 7 failed" - an index. An operator needs the slug."""
    client = FakeClient(
        repositories=[repository("broken")],
        listings={},
        listing_errors={"broken": status_error(500)},
    )

    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        with pytest.raises(OceanAbortException):
            async for _ in process_file_patterns(
                BitbucketFilePattern(path="/", filenames=["README.md"]), {}
            ):
                pass

    assert any(
        "File discovery failed for repository broken on branch main" in message
        for message in error_messages
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403, 500])
async def test_no_status_short_circuits_the_walk(status_code: int) -> None:
    """Not even a 401. Under MultiTokenAuth it is one token out of a rotating pool,
    not the workspace, so abandoning the walk would strand the repositories the other
    tokens can still read."""
    client = FakeClient(
        repositories=[],
        repository_batches=[[repository("first")], [repository("second")]],
        listings={"second": [[listing_entry("README.md")]]},
        listing_errors={"first": status_error(status_code)},
    )

    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        results: List[Dict[str, Any]] = []
        with pytest.raises(OceanAbortException):
            async for batch in process_file_patterns(
                BitbucketFilePattern(path="/", filenames=["README.md"]), {}
            ):
                results.extend(batch)

    assert client.listed_slugs == ["first", "second"]
    assert [result["metadata"]["path"] for result in results] == ["README.md"]


@pytest.mark.asyncio
async def test_a_server_error_does_not_stop_the_walk() -> None:
    """One bad repository must not cost the healthy ones still to come."""
    client = FakeClient(
        repositories=[],
        repository_batches=[[repository("first")], [repository("second")]],
        listings={"second": [[listing_entry("README.md")]]},
        listing_errors={"first": status_error(500)},
    )

    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        results: List[Dict[str, Any]] = []
        with pytest.raises(OceanAbortException):
            async for batch in process_file_patterns(
                BitbucketFilePattern(path="/", filenames=["README.md"]), {}
            ):
                results.extend(batch)

    assert client.listed_slugs == ["first", "second"]
    assert [result["metadata"]["path"] for result in results] == ["README.md"]


@pytest.mark.asyncio
async def test_absent_configured_path_logs_no_error(
    error_messages: List[str],
) -> None:
    """A repository that simply has no such directory is routine, not an error."""
    client = FakeClient(
        repositories=[repository("repo-a")],
        listings={"repo-a": [[]]},
        errors_by_path={"charts": not_found()},
    )

    await discover(
        client, BitbucketFilePattern(path="charts/*", filenames=["port.yml"])
    )

    assert error_messages == []


@pytest.mark.parametrize(
    "file_path, filename, matches",
    [
        ("port.yml", "port.yml", True),
        ("charts/app/port.yml", "port.yml", True),
        ("airport.yml", "port.yml", False),
        ("charts/airport.yml", "port.yml", False),
        ("buyorbid/conf/README.md", "conf/README.md", True),
        ("myconf/README.md", "conf/README.md", False),
        # An extension is not a filename. `endswith` accepted one by accident, which
        # is the same accident that accepted airport.yml.
        ("port.yml", ".yml", False),
        ("charts/port.yml", ".yml", False),
    ],
)
def test_filename_matches_on_a_path_boundary(
    file_path: str, filename: str, matches: bool
) -> None:
    """endswith alone accepts airport.yml for a configured port.yml."""
    assert filename_matches(file_path, filename) is matches


@pytest.mark.asyncio
async def test_a_suffix_lookalike_is_not_discovered() -> None:
    """The boundary rule reaches discovery, not just the predicate.

    The default ``*/`` path is what makes this visible: it normalizes to ``*``, which
    fnmatch accepts for the ``air`` left over after stripping ``port.yml``, so the path
    half of the check cannot catch the lookalike.
    """
    client = FakeClient(
        repositories=[repository("repo")],
        listings={"repo": [[listing_entry("airport.yml"), listing_entry("port.yml")]]},
    )

    results = await discover(
        client, BitbucketFilePattern(path="*/", filenames=["port.yml"])
    )

    assert [result["metadata"]["path"] for result in results] == ["port.yml"]


@pytest.mark.asyncio
async def test_a_file_whose_content_cannot_be_read_aborts_the_kind() -> None:
    """The listing proved the file exists at this immutable commit, so a failed read
    is a failure, not an absence. Omitting the entity would not protect it: the resync
    would complete and reconciliation would delete it.

    The cost, measured here: stream_async_iterators_tasks fails fast, so the sibling
    file being fetched in the same page is cancelled and this repository contributes
    nothing. Other repositories still yield - see
    test_listing_failure_aborts_after_healthy_repositories_yield. Nothing is deleted
    either way, which is the point.
    """
    client = FakeClient(
        repositories=[repository("repo")],
        listings={"repo": [[listing_entry("port.yml"), listing_entry("other.yml")]]},
        contents={"port.yml": None},
    )

    with patch("bitbucket_cloud.helpers.file_kind.init_client", return_value=client):
        results: List[Dict[str, Any]] = []
        with pytest.raises(OceanAbortException):
            async for batch in process_file_patterns(
                BitbucketFilePattern(
                    path="/", filenames=["port.yml", "other.yml"], skipParsing=True
                ),
                {},
            ):
                results.extend(batch)

    assert results == []


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("port.yml", 'path~"port.yml"'),
        # Unescaped, this is HTTP 500 for the whole repository (measured). Escaped,
        # Bitbucket answers 200 and matches the quote literally.
        ('po"rt.yml', 'path~"po\\"rt.yml"'),
        ("back\\slash.yml", 'path~"back\\\\slash.yml"'),
    ],
)
def test_configured_filenames_are_escaped_into_the_filter(
    filename: str, expected: str
) -> None:
    assert build_file_filter([filename]) == f'type="commit_file" AND ({expected})'


def test_escape_bbql_string_escapes_the_backslash_before_the_quote() -> None:
    """Order matters: quote-first would double-escape the backslash it just added."""
    assert escape_bbql_string('a\\"b') == 'a\\\\\\"b'
