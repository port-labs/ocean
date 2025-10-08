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
    # NOTE: we'll special-case pure string literals before other checks
    r"^\s*\[.*\]\s*$",  # array literal (we'll ensure no '.' after masking strings)
    r"^\s*\{.*\}\s*$",  # object literal (same)
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


# String literal handling (jq uses double quotes for strings)
_STRING_LITERAL_RE = re.compile(r'"(?:\\.|[^"\\])*"')
_STRING_ONLY_RE = re.compile(r'^\s*"(?:\\.|[^"\\])*"\s*$')


def _mask_strings(expr: str) -> str:
    """Replace string literals with empty strings so '.' inside quotes don’t count."""
    return _STRING_LITERAL_RE.sub("", expr)


def should_shortcut_no_input(selector_query: str) -> bool:
    """
    Returns True if the jq expression can be executed without providing any JSON input.
    Rules:
      - Whitespace-only => NONE
      - A pure string literal => NONE (even if it contains '.')
      - After masking strings, if it contains '.' => needs input
      - Disallow known input-dependent functions
      - Allow null/true/false/number/range/empty, and array/object literals that
        don’t reference input (no '.' after masking strings)
    """
    s = selector_query.strip()
    if s == "":
        return True  # whitespace-only

    # Pure string literal is nullary
    if _STRING_ONLY_RE.match(s):
        return True

    masked = _mask_strings(s)

    # If it contains any known input-dependent functions, don't shortcut
    if _INPUT_DEPENDENT_RE.search(masked):
        return False

    # Any '.' outside of strings means it references input
    if "." in masked:
        return False

    # Allow basic nullary forms
    for pat in _ALLOWLIST_PATTERNS:
        if re.match(pat, masked):
            return True

    return False


def _has_rootish_single_selector(expr: str, key: str) -> bool:
    """
    Detect `.key` outside of quotes, as a standalone path segment beginning
    after a non-word boundary (start, space, |, (, [, {, , or :) and not part
    of `.something.key`.
    """
    if not key:
        return False

    masked = _mask_strings(expr)
    pattern = re.compile(rf"(?<![A-Za-z0-9_])\.{re.escape(key)}(?![A-Za-z0-9_])")
    return bool(pattern.search(masked))


def evaluate_input(
    selector_query: str, single_item_key: str | None = None
) -> InputEvaluationResult:
    """
    Returns the input evaluation result for the jq expression.
    Conservative: requires NO '.' and must match a known nullary-safe pattern.
    """
    if should_shortcut_no_input(selector_query):
        return InputEvaluationResult.NONE
    if single_item_key and _has_rootish_single_selector(
        selector_query, single_item_key
    ):
        return InputEvaluationResult.SINGLE
    return InputEvaluationResult.ALL
