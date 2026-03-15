from port_ocean.core.utils.included_files import resolve_included_file_path


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
