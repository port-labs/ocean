import fnmatch
from enum import StrEnum
from dataclasses import dataclass


class ObjectKind(StrEnum):
    PROJECT = "project"
    FOLDER = "folder"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    FILE = "file"


@dataclass
class BitbucketRateLimiterConfig:
    """Configuration for Bitbucket API rate limiting."""

    WINDOW: int = 3600  # Rate limit window in seconds
    LIMIT: int = 980  # Number of requests allowed per window


@dataclass
class BitbucketFileRateLimiterConfig:
    """Configuration for Bitbucket file content API rate limiting."""

    WINDOW: int = 3600  # Rate limit window in seconds
    LIMIT: int = 4980  # Number of requests allowed per window for file operations


GLOBAL_PATHS = ["*/", "*", "**/*", "**", ""]


def normalize_directory_path(path: str) -> str:
    """Strip leading and trailing slashes so path variants match equivalently.

    ``hello/world``, ``/hello/world``, ``/hello/world/``, and ``hello/world/``
    all normalize to ``hello/world``. Root ``/`` and empty become ``""``.
    """
    return path.strip("/")


def filename_matches(file_path: str, filename: str) -> bool:
    """Match a configured filename against the tail of a repository-relative path.

    ``endswith`` on its own accepts ``airport.yml`` for a configured ``port.yml``, so
    the match has to land on a path boundary. A configured value that already carries
    directories, ``conf/README.md``, still matches at that boundary.
    """
    return file_path == filename or file_path.endswith(f"/{filename}")


def validate_file_match(file_path: str, filename: str, expected_path: str) -> bool:
    """Validate if the file path and filename match the expected patterns."""
    if not filename_matches(file_path, filename):
        return False

    if (not expected_path or expected_path == "/") and file_path == filename:
        return True

    if expected_path in GLOBAL_PATHS:
        expected_path = "*/"

    dir_path = normalize_directory_path(file_path[: -len(filename)])
    expected_path = normalize_directory_path(expected_path)
    return fnmatch.fnmatch(dir_path, expected_path)


def matches_configured_file(
    file_path: str, filenames: list[str], configured_path: str
) -> bool:
    """The one filename/path matcher for the `file` kind.

    Both the resync walk and the push handler call this. They previously each had
    their own: the walk matched the whole path against a path-boundary suffix, the
    handler fnmatched the basename only, so one config could be discovered by one and
    ignored by the other.
    """
    return any(
        validate_file_match(file_path, filename, configured_path)
        for filename in filenames
    )
