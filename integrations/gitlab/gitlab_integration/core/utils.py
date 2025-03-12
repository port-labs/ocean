from typing import List, Union

from braceexpand import braceexpand  # type: ignore
from glob2 import fnmatch  # type: ignore


def does_pattern_apply(patterns: Union[str, List[str]], string: str) -> bool:
    """
    Returns True if `pathname` matches at least one of the patterns in `patterns`.
    We handle the special case where a pattern starts with '**/' by also
    checking the bare pattern (e.g. '**/file.yml' => 'file.yml').
    """
    if isinstance(patterns, str):
        patterns = [patterns]

    for pattern in patterns:
        if pattern.startswith("**/"):
            # Also try the pattern without '**/' to allow matching a bare filename.
            bare_pattern = pattern.replace("**/", "", 1)
            if fnmatch.fnmatch(string, pattern) or fnmatch.fnmatch(
                string, bare_pattern
            ):
                return True
        else:
            if fnmatch.fnmatch(string, pattern):
                return True

    return False


def convert_glob_to_gitlab_patterns(pattern: Union[str, List[str]]) -> List[str]:
    """Converts glob patterns into GitLab-compatible patterns."""
    if isinstance(pattern, list):
        expanded_patterns: list[str] = []
        for glob_pattern in pattern:
            expanded_patterns.extend(braceexpand(glob_pattern))
        return expanded_patterns

    # Handle case where the input is a single pattern
    return list(braceexpand(pattern))


def generate_ref(branch_name: str) -> str:
    return f"refs/heads/{branch_name}"
