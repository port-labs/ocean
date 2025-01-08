import fnmatch


def _match(pattern_parts: list[str], string_parts: list[str]) -> bool:
    if not pattern_parts:  # Reached the end of the pattern
        return not string_parts
    if not string_parts:  # Reached the end of the string
        return pattern_parts == ["**"]

    if pattern_parts[0] == "**":
        if len(pattern_parts) == 1:
            return True
        else:  # Recursive matching
            return _match(pattern_parts[1:], string_parts) or _match(
                pattern_parts, string_parts[1:]
            )

    if fnmatch.fnmatch(string_parts[0], pattern_parts[0]):  # Regular matching
        return _match(pattern_parts[1:], string_parts[1:])
    return False


def does_pattern_apply(pattern: str | list[str], string: str) -> bool:
    if isinstance(pattern, list):
        return any(
            does_pattern_apply(single_pattern, string) for single_pattern in pattern
        )

    pattern_parts = pattern.split("/")
    string_parts = string.split("/")
    return _match(pattern_parts, string_parts)


def generate_ref(branch_name: str) -> str:
    return f"refs/heads/{branch_name}"
