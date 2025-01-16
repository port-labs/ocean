from glob2 import fnmatch
from typing import Union, List


def does_pattern_apply(pattern: Union[str, List[str]], string: str) -> bool:
    if isinstance(pattern, list):
        return any(does_pattern_apply(p, string) for p in pattern)
    return fnmatch.fnmatch(string, pattern)

def generate_ref(branch_name: str) -> str:
    return f"refs/heads/{branch_name}"
