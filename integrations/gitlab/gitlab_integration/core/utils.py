from glob2 import fnmatch  # type: ignore
from typing import Union, List
from braceexpand import braceexpand


def does_pattern_apply(pattern: Union[str, List[str]], string: str) -> bool:
    if isinstance(pattern, list):
        return any(does_pattern_apply(p, string) for p in pattern)
    return fnmatch.fnmatch(string, pattern)


def convert_glob_to_gitlab_patterns(pattern: Union[str, List[str]]) -> List[str]:
    """Converts glob patterns into GitLab-compatible patterns."""
    if isinstance(pattern, list):
        return [p for pat in pattern for p in braceexpand(pat)]
    return list(braceexpand(pattern))


def generate_ref(branch_name: str) -> str:
    return f"refs/heads/{branch_name}"
