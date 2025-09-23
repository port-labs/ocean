import re
from enum import Enum


class InputEvaluationResult(Enum):
    NONE = 1
    SINGLE = 2
    ALL = 3


# Conservative allowlist: truly nullary jq expressions
_ALLOWLIST_PATTERNS = [
    r"^\s*null\s*$",  # null
    r"^\s*true\s*$",  # true
    r"^\s*false\s*$",  # false
    r"^\s*-?\d+(\.\d+)?\s*$",  # number literal
    r'^\s*".*"\s*$',  # string literal (simple heuristic)
    r"^\s*\[.*\]\s*$",  # array literal (includes [])
    r"^\s*\{.*\}\s*$",  # object literal (includes {})
    r"^\s*range\s*\(.*\)\s*$",  # range(...)
    r"^\s*empty\s*$",  # empty
]

# Functions/filters that (even without ".") still require/assume input
_INPUT_DEPENDENT_FUNCS = r"""
\b(
    map|select|reverse|sort|sort_by|unique|unique_by|group_by|flatten|transpose|
    split|explode|join|add|length|has|in|index|indices|contains|
    paths|leaf_paths|keys|keys_unsorted|values|to_entries|with_entries|from_entries|
    del|delpaths|walk|reduce|foreach|input|inputs|limit|first|last|nth|
    while|until|recurse|recurse_down|bsearch|combinations|permutations
)\b
"""

_INPUT_DEPENDENT_RE = re.compile(_INPUT_DEPENDENT_FUNCS, re.VERBOSE)


def should_shortcut_no_input(selector_query: str) -> bool:
    """
    Returns True if the jq expression can be executed without providing any JSON input.
    Conservative: requires NO '.' and must match a known nullary-safe pattern.
    """
    if "." in selector_query:
        return False  # explicit JSON reference -> needs input

    # If it contains any known input-dependent functions, don't shortcut
    if _INPUT_DEPENDENT_RE.search(selector_query):
        return False

    # Allow only if it matches one of the nullary-safe patterns
    for pat in _ALLOWLIST_PATTERNS:
        if re.match(pat, selector_query):
            return True

    return False


def evaluate_input(
    selector_query: str, single_item_key: str | None = None
) -> InputEvaluationResult:
    """
    Returns the input evaluation result for the jq expression.
    Conservative: requires NO '.' and must match a known nullary-safe pattern.
    """
    if should_shortcut_no_input(selector_query):
        return InputEvaluationResult.NONE
    if single_item_key and single_item_key in selector_query:
        return InputEvaluationResult.SINGLE
    return InputEvaluationResult.ALL
