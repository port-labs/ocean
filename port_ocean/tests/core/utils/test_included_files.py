from dataclasses import dataclass

from port_ocean.core.utils.included_files import (
    repo_branch_matches,
    resolve_included_file_path,
)


@dataclass
class _RepoMapping:
    name: str
    branch: str | None


class TestRepoBranchMatches:
    def test_default_branch_only_when_no_repos_mapping(self) -> None:
        assert (
            repo_branch_matches(
                repos=None,
                repo_name="Port",
                branch="main",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=None,
                repo_name="Port",
                branch="dev",
                default_branch="main",
            )
            is False
        )

    def test_explicit_branch_mapping(self) -> None:
        repos = [_RepoMapping(name="Port", branch="dev")]
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="dev",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="main",
                default_branch="main",
            )
            is False
        )

    def test_none_branch_mapping_means_default_branch(self) -> None:
        repos = [_RepoMapping(name="Port", branch=None)]
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="main",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="dev",
                default_branch="main",
            )
            is False
        )

    def test_default_branch_special_value(self) -> None:
        repos = [_RepoMapping(name="Port", branch="default")]
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="main",
                default_branch="main",
            )
            is True
        )
        assert (
            repo_branch_matches(
                repos=repos,
                repo_name="Port",
                branch="dev",
                default_branch="main",
            )
            is False
        )


class TestResolveIncludedFilePath:
    def test_repo_root_leading_slash_when_no_base(self) -> None:
        assert resolve_included_file_path("/README.md", base_path="") == "README.md"

    def test_relative_to_base_when_base_present(self) -> None:
        assert (
            resolve_included_file_path("README.md", base_path="remote")
            == "remote/README.md"
        )

    def test_does_not_double_join_when_requested_already_includes_base(self) -> None:
        assert (
            resolve_included_file_path("remote/README.md", base_path="remote")
            == "remote/README.md"
        )
        assert (
            resolve_included_file_path("/remote/README.md", base_path="remote")
            == "remote/README.md"
        )

    def test_dot_base_treated_as_empty(self) -> None:
        assert resolve_included_file_path("/README.md", base_path=".") == "README.md"
        assert resolve_included_file_path("README.md", base_path=".") == "README.md"

    def test_empty_requested_path_returned_unchanged(self) -> None:
        assert resolve_included_file_path("", base_path="") == ""
        assert resolve_included_file_path("", base_path="remote") == ""
