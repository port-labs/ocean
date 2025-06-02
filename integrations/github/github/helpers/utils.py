from enum import StrEnum
import re


class GithubClientType(StrEnum):
    REST = "rest"
    GRAPHQL = "graphql"


class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    FOLDER = "folder"


def translate_glob_pattern(pattern) -> str:
    """
    Translates a glob-style pattern into a regular expression pattern.
    Mimics glob.translate from Python 3.13 for older versions.
    """
    i, n = 0, len(pattern)
    res = ""
    while i < n:
        c = pattern[i]
        i += 1
        if c == "*":
            res += ".*"
        elif c == "?":
            res += "."
        elif c == "[":
            j = i
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j < n:
                seq = pattern[i:j]
                i = j + 1
                if seq[0] == "!":
                    # Character class and its contents must be escaped for regex
                    seq = "[^" + re.escape(seq[1:]) + "]"
                else:
                    seq = "[" + re.escape(seq) + "]"
                res += seq
            else:
                res += re.escape(c)
        else:
            res += re.escape(c)
    return res
