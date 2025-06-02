import pytest
from github.helpers.utils import translate_glob_pattern


class TestTranslateGlobPattern:
    @pytest.mark.parametrize(
        "pattern, expected",
        [
            ("", ""),
            ("file.txt", "file\\.txt"),
            ("*.txt", ".*\\.txt"),
            ("image_?.png", "image_\\.png"),
            ("dir/*", "dir/.*"),
            (
                "data/**",
                "data/.*.*",
            ),  # ** is not special for glob.translate, becomes * *
            ("path/to/*.csv", "path/to/.*\\.csv"),
            ("test_file_?.log", "test_file_\\.log"),
            ("foo\\bar", "foo\\\\bar"),  # Escaped backslash
            ("foo[bar]", "foo[bar]"),
            ("foo[!bar]", "foo[^bar]"),
            (
                "foo[a-z]",
                "foo[a\\\\-z]",
            ),  # hyphen inside char class is escaped by re.escape
            (
                "foo[!a-z]",
                "foo[^a\\\\-z]",
            ),  # hyphen inside char class is escaped by re.escape
            ("foo[0-9].txt", "foo[0\\\\-9]\\.txt"),
            ("foo[A-Za-z_].py", "foo[A\\\\-Za\\\\-z_]\\.py"),
            ("dir/[abc].txt", "dir/[abc]\\.txt"),
            ("dir/[!abc].txt", "dir/[^abc]\\.txt"),
            (
                "file[].txt",
                "file[]\\.txt",
            ),  # empty char class, *not* treated as literal [ ], it's a character class matching nothing
            ("file[!].txt", "file[^]\\.txt"),  # ! char class, results in [^]
            (
                "file[!]name.txt",
                "file[^]name\\.txt",
            ),  # special case for [!] -> results in [^]
            ("file[a^b].txt", "file[a\\^b]\\.txt"),  # ^ inside char class escaped
            (
                "file[a-b\\c].txt",
                "file[a\\\\-b\\\\c]\\.txt",
            ),  # - and \ inside char class escaped
            ("leading_wildcard*", "leading_wildcard.*"),
            ("*trailing_wildcard", ".*trailing_wildcard"),
            ("a*b*c", "a.*b.*c"),
            ("a?b?c", "a.b.c"),
            ("file[", "file\\["),  # Unclosed bracket
            ("file[!", "file\\[!"),  # Unclosed bracket with !
            ("file[!abc", "file\\[!abc"),  # Unclosed bracket with content and !
            ("file[abc", "file\\[abc"),  # Unclosed bracket with content
            ("file[]", "file[]"),  # Empty character set
            ("file[^]", "file[^]"),  # Literal ^ inside [] that's not at the start
            ("file[\\^]", "file[\\\\^]"),  # Escaped ^ inside []
            ("file[\\\\]", "file[\\\\\\]"),  # Escaped \ inside []
            ("file[.txt]", "file[\\.txt]"),  # . inside char class
            ("file[-abc]", "file[\\-abc]"),  # - at start of char class (literal)
            ("file[abc-]", "file[abc\\-]"),  # - at end of char class (literal)
            ("file[a-c]", "file[a\\\\-c]"),  # Range - is escaped by re.escape
        ],
    )
    def test_translate_glob_pattern(self, pattern, expected):
        assert translate_glob_pattern(pattern) == expected
