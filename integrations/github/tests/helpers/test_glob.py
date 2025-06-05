import os
import re
from typing import Any, Callable, Optional, Sequence
import pytest
from github.helpers.glob import translate_glob


def _get_sep_regex(seps: Optional[Sequence[str]]) -> str:
    if seps is None:
        if os.path.altsep:
            seps = (os.path.sep, os.path.altsep)
        else:
            seps = (os.path.sep,)
    escaped_seps = "".join(map(re.escape, seps))
    return f"[{escaped_seps}]" if len(escaped_seps) > 1 else escaped_seps


def _get_not_sep_regex(seps: Optional[Sequence[str]]) -> str:
    if seps is None:
        if os.path.altsep:
            seps = (os.path.sep, os.path.altsep)
        else:
            seps = (os.path.sep,)
    escaped_seps = "".join(map(re.escape, seps))
    return f"[^{escaped_seps}]"


def _get_one_last_segment_regex(seps: Sequence[str], include_hidden: bool) -> str:
    not_sep = _get_not_sep_regex(seps)
    if include_hidden:
        return f"{not_sep}+"
    else:
        return f"[^{_get_sep_regex(seps)}.]({not_sep})*"


def _get_one_segment_regex(seps: Sequence[str], include_hidden: bool) -> str:
    one_last_segment = _get_one_last_segment_regex(seps, include_hidden)
    any_sep = _get_sep_regex(seps)
    return f"{one_last_segment}{any_sep}"


def _get_any_segments_regex(seps: Sequence[str], include_hidden: bool) -> str:
    any_sep = _get_sep_regex(seps)
    one_segment = _get_one_segment_regex(seps, include_hidden)
    if include_hidden:
        return f"(?:.+{any_sep})?"
    else:
        return f"(?:{one_segment})*"


def _get_any_last_segments_regex(seps: Sequence[str], include_hidden: bool) -> str:
    if include_hidden:
        return ".*"
    else:
        any_segments = _get_any_segments_regex(seps, include_hidden)
        one_last_segment = _get_one_last_segment_regex(seps, include_hidden)
        return f"{any_segments}(?:{one_last_segment})?"


class TestTranslateGlobPattern:
    @pytest.mark.parametrize(
        "pattern, recursive, include_hidden, seps, expected_func",
        [
            # Basic functionality (recursive=False, include_hidden=False, seps=None)
            (
                "*.txt",
                False,
                False,
                None,
                lambda s,
                h,
                se: rf"(?s:(?!\.){_get_one_last_segment_regex(se, h)}\.txt)\Z",
            ),
            (
                "foo/bar.py",
                False,
                False,
                None,
                lambda s, h, se: rf"(?s:foo{_get_sep_regex(se)}bar\.py)\Z",
            ),
            (
                "foo?.txt",
                False,
                False,
                None,
                lambda s,
                h,
                se: rf"(?s:(?!\.)foo\.{_get_one_last_segment_regex(se, h)}\.txt)\Z",
            ),
            (
                "dir/*",
                False,
                False,
                None,
                lambda s,
                h,
                se: rf"(?s:dir{_get_sep_regex(se)}(?!\.){_get_one_last_segment_regex(se, h)})\Z",
            ),
            (
                "foo/[abc].txt",
                False,
                False,
                None,
                lambda s, h, se: rf"(?s:foo{_get_sep_regex(se)}[abc]\.txt)\Z",
            ),
            (
                "foo/[!abc].txt",
                False,
                False,
                None,
                lambda s, h, se: rf"(?s:foo{_get_sep_regex(se)}[^abc]\.txt)\Z",
            ),
            (
                "path/to/*.csv",
                False,
                False,
                None,
                lambda s,
                h,
                se: rf"(?s:path{_get_sep_regex(se)}to{_get_sep_regex(se)}(?!\.){_get_one_last_segment_regex(se, h)}\.csv)\Z",
            ),
            # recursive=True (**) (include_hidden=False, seps=None)
            (
                "data/**",
                True,
                False,
                None,
                lambda s,
                h,
                se: rf"(?s:data{_get_sep_regex(se)}{_get_any_last_segments_regex(se, h)})\Z",
            ),
            (
                "**/file.txt",
                True,
                False,
                None,
                lambda s, h, se: rf"(?s:{_get_any_segments_regex(se, h)}file\.txt)\Z",
            ),  # ** does not add (?!\.)
            (
                "foo/**/bar.txt",
                True,
                False,
                None,
                lambda s,
                h,
                se: rf"(?s:foo{_get_sep_regex(se)}{_get_any_segments_regex(se, h)}bar\.txt)\Z",
            ),
            (
                "**",
                True,
                False,
                None,
                lambda s, h, se: rf"(?s:{_get_any_last_segments_regex(se, h)})\Z",
            ),
            (
                "foo/**/bar/**/baz.txt",
                True,
                False,
                None,
                lambda s,
                h,
                se: rf"(?s:foo{_get_sep_regex(se)}{_get_any_segments_regex(se, h)}bar{_get_sep_regex(se)}{_get_any_segments_regex(se, h)}baz\.txt)\Z",
            ),
            # include_hidden=True (recursive=False, seps=None)
            (".git", False, True, None, lambda s, h, se: r"(?s:\.git)\Z"),
            (".*", False, True, None, lambda s, h, se: r"(?s:.*)\Z"),
            (
                "src/.hidden/file.txt",
                False,
                True,
                None,
                lambda s,
                h,
                se: rf"(?s:src{_get_sep_regex(se)}\.hidden{_get_sep_regex(se)}file\.txt)\Z",
            ),
            (
                "src/*",
                False,
                True,
                None,
                lambda s,
                h,
                se: rf"(?s:src{_get_sep_regex(se)}{_get_one_last_segment_regex(se, h)})\Z",
            ),  # No (?!\.) for include_hidden=True
            (
                "*/",
                False,
                True,
                None,
                lambda s, h, se: rf"(?s:{_get_one_segment_regex(se, h)})\Z",
            ),  # No (?!\.) for include_hidden=True
            # include_hidden=True and recursive=True
            (
                "src/**/.hidden/file.txt",
                True,
                True,
                None,
                lambda s,
                h,
                se: rf"(?s:src{_get_sep_regex(se)}{_get_any_segments_regex(se, h)}\.hidden{_get_sep_regex(se)}file\.txt)\Z",
            ),
            (
                "**/.*",
                True,
                True,
                None,
                lambda s, h, se: rf"(?s:{_get_any_segments_regex(se, h)}.*)\Z",
            ),
            # seps parameter
            (
                "foo\\bar.txt",
                False,
                False,
                ("\\",),
                lambda s, h, se: r"(?s:foo\\bar\.txt)\Z",
            ),
            (
                "foo/bar.txt",
                False,
                False,
                ("/",),
                lambda s, h, se: r"(?s:foo/bar\.txt)\Z",
            ),
            (
                "foo\\**\\bar.txt",
                True,
                False,
                ("\\",),
                lambda s,
                h,
                se: rf"(?s:foo\\{_get_any_segments_regex(se, h)}bar\.txt)\Z",
            ),
            (
                "foo/bar\\baz.txt",
                False,
                False,
                ("/", "\\"),
                lambda s, h, se: r"(?s:foo[/\\]bar[/\\]baz\.txt)\Z",
            ),
            (
                "foo/**/bar",
                True,
                False,
                ("/",),
                lambda s, h, se: rf"(?s:foo/{_get_any_segments_regex(se, h)}bar)\Z",
            ),
            ("foo/bar", False, False, ("/",), lambda s, h, se: r"(?s:foo/bar)\Z"),
            (
                "*",
                False,
                False,
                ("/",),
                lambda s,
                h,
                se: rf"(?s:(?!\.)[^{re.escape('/')}.][^{re.escape('/')}]*)\Z",
            ),
            # Edge Cases
            ("", False, False, None, lambda s, h, se: r"(?s:)\Z"),
            (
                "/",
                False,
                False,
                None,
                lambda s, h, se: rf"(?s:{_get_sep_regex(se)})\Z",
            ),
            (
                "a/b/c",
                False,
                False,
                None,
                lambda s, h, se: rf"(?s:a{_get_sep_regex(se)}b{_get_sep_regex(se)}c)\Z",
            ),
            (
                "a//b",
                False,
                False,
                None,  # double sep
                lambda s, h, se: rf"(?s:a{_get_sep_regex(se)}{_get_sep_regex(se)}b)\Z",
            ),
            (
                "a*b",
                False,
                False,
                None,
                lambda s, h, se: r"(?s:a.*b)\Z",
            ),  # No (?!\.) because part[0] is 'a'
            (
                "a?b",
                False,
                False,
                None,
                lambda s, h, se: r"(?s:a.b)\Z",
            ),  # No (?!\.) because part[0] is 'a'
        ],
    )
    def test_translate_glob(
        self,
        pattern: str,
        recursive: bool,
        include_hidden: bool,
        seps: Optional[Sequence[str]],
        expected_func: Callable[[bool, bool, Any | None], str],
    ) -> None:
        expected_regex = expected_func(recursive, include_hidden, seps)
        result = translate_glob(
            pattern, recursive=recursive, include_hidden=include_hidden, seps=seps
        )
        assert result == expected_regex
