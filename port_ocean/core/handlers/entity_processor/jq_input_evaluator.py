import re
from enum import Enum

# This file is used to classify the input that a jq expression to run on.
# It is used to determine if the jq expression can be executed without providing any JSON input (const expressions)
# or on a single item (in items to parse situation)
# or on all the data


class InputClassifyingResult(Enum):
    NONE = 1
    SINGLE = 2
    ALL = 3


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
_NUMBER_ONLY_RE = re.compile(r"^\s*-?\d+(\.\d+)?\s*$")


def _mask_strings(expr: str) -> str:
    """
    Replace string literals with 'S' strings so '.' inside quotes don't count.
    Example:
        - '"this is a string"' ---> 'S'
        - '"sting" + .field'. ---> 'S + .field'
    """
    return _STRING_LITERAL_RE.sub("S", expr)


def _mask_numbers(expr: str) -> str:
    """
    Replace number literals with 'N' so decimal points in numbers don't count as input references.
    Example:
        - '3.14' ---> 'N'
        - '42 + 3.14' ---> 'N + N'
    """
    # Pattern to match numbers (integers and decimals, with optional sign)
    number_pattern = re.compile(r"[-+]?\d+(?:\.\d+)?")
    return number_pattern.sub("N", expr)


def can_expression_run_with_no_input(selector_query: str) -> bool:
    """
    Returns True if the jq expression can be executed without providing any JSON input.
    Rules:
      - Whitespace-only => No Input Required
      - A pure string literal => No Input Required (even if it contains '.')
      - After masking strings, if it contains '.' => Input Required
      - Disallow known input-dependent functions (functions that require input)
      - After masking strings, if it contains only operators and numbers and 'S' => No Input Required
      - Allow null/true/false/number/range/empty, and array/object literals that
        don't reference input (no '.' after masking strings) => No Input Required
    Example:
        - blueprint: '"newRelicService"' in mapping, selector_query param would be '"newRelicService"' => No Input Required
    """
    s = selector_query.strip()
    if s == "":
        return True  # whitespace-only

    # Pure string literal is nullary
    if _STRING_ONLY_RE.match(s):
        return True

    # First mask strings, then mask numbers to prevent decimal points in numbers from being treated as input references
    masked = _mask_strings(s).strip()
    masked = _mask_numbers(masked).strip()

    # If it contains any known input-dependent functions, don't shortcut
    if _INPUT_DEPENDENT_RE.search(masked):
        return False

    # If it contains only operators and 'S'/'N', it can be executed with no input
    # Example:
    # - '"abc" + "def"' ---> 'S + S' => No Input Required
    # - '3.14 + 2.5' ---> 'N + N' => No Input Required
    # if re.fullmatch(
    #     r"(?:S|N)(?:\s*[+\-*/]\s*(?:S|N))*",
    #     masked,
    # ):
    #     return True

    if "." not in masked:
        return True

    return False


def _can_expression_run_on_single_item(expr: str, key: str) -> bool:
    """
    Return True only if all top-level jq paths in the expression
    reference `.key...` and nothing outside that tree.
    """
    if not key:
        return False

    masked = _mask_strings(expr)
    masked = _mask_numbers(masked)

    # 🚫 Reject expressions that start from a root-level array, e.g. `.[] | ...` or `.[0] | ...`
    # Top-level ".[" = a dot not preceded by [A-Za-z0-9_.])]
    if re.search(r"(?<![A-Za-z0-9_.\]\)])\.\[", masked):
        return False

    # Match *top-level* paths only:
    # - A dot NOT preceded by [A-Za-z0-9_.])]
    #   (so we don't treat `.field` in `.item.field[0].subfield` as a new root)
    # - Followed by an identifier for the first segment
    paths = re.findall(
        r"(?<![A-Za-z0-9_.\]\)])\.[A-Za-z_][A-Za-z0-9_]*",
        masked,
    )

    if not paths:
        return False

    allowed_root = f".{key}"

    for p in paths:
        if p == allowed_root or p.startswith(allowed_root + "."):
            continue
        else:
            # Some other root field like .name, .body, .foo, etc.
            return False

    return True


def classify_input(
    selector_query: str, single_item_key: str | None = None
) -> InputClassifyingResult:
    """
    Returns the input evaluation result for the jq expression.
    Conservative: requires NO '.' and must match a known nullary-safe pattern.
    """
    if can_expression_run_with_no_input(selector_query):
        return InputClassifyingResult.NONE
    if single_item_key and _can_expression_run_on_single_item(
        selector_query, single_item_key
    ):
        return InputClassifyingResult.SINGLE
    return InputClassifyingResult.ALL
