from datetime import datetime, timedelta, timezone

from jira.helpers.incremental import apply_cursor_to_jql

CURSOR = datetime(2026, 10, 13, 15, 45, 45, tzinfo=timezone.utc)
# The cursor as unquoted epoch milliseconds.
BOUND = "updated >= 1791906345000"


def test_returns_jql_unchanged_on_full_resync() -> None:
    jql = "project = TEST ORDER BY created DESC"
    assert apply_cursor_to_jql(jql, None) == jql


def test_bound_is_unquoted_epoch_milliseconds() -> None:
    """Quoted literals have no offset form and resolve in the user's time zone."""
    result = apply_cursor_to_jql("project = TEST", CURSOR)

    assert result == f"(project = TEST) AND {BOUND}"
    assert '"' not in result.split("AND")[-1]


def test_bound_is_the_cursor_itself_with_no_margin() -> None:
    """A margin would re-fetch data the cursor already covered; the full resync
    is what covers a change the search index was late to surface."""
    assert (
        apply_cursor_to_jql("", CURSOR)
        == f"updated >= {int(CURSOR.timestamp() * 1000)}"
    )


def test_bound_keeps_sub_minute_precision() -> None:
    """Epoch bounds need no flooring, so a second's difference still moves them."""
    later = apply_cursor_to_jql("", CURSOR + timedelta(seconds=1))
    assert later != BOUND
    assert later == "updated >= 1791906346000"


def test_a_naive_cursor_is_read_as_utc_not_container_local() -> None:
    """The cursor's type promises no offset; timestamp() would read naive as local."""
    naive = CURSOR.replace(tzinfo=None)
    assert apply_cursor_to_jql("", naive) == apply_cursor_to_jql("", CURSOR) == BOUND


def test_a_cursor_in_another_offset_normalises_to_the_same_instant() -> None:
    shifted = CURSOR.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert apply_cursor_to_jql("", shifted) == BOUND


def test_wraps_existing_filters_so_or_clauses_stay_scoped() -> None:
    result = apply_cursor_to_jql("a = 1 OR b = 2", CURSOR)
    assert result == f"(a = 1 OR b = 2) AND {BOUND}"


def test_window_goes_before_order_by() -> None:
    result = apply_cursor_to_jql("project = TEST order by created DESC", CURSOR)
    assert result == f"(project = TEST) AND {BOUND} order by created DESC"


def test_order_by_inside_a_quoted_value_is_not_a_clause() -> None:
    result = apply_cursor_to_jql('summary ~ "order by milk"', CURSOR)
    assert result == f'(summary ~ "order by milk") AND {BOUND}'


def test_order_by_inside_an_escaped_quote_is_not_a_clause() -> None:
    """Splitting here would emit JQL that Jira rejects, failing the whole run."""
    jql = 'summary ~ "say \\"order by\\" twice"'
    assert apply_cursor_to_jql(jql, CURSOR) == f"({jql}) AND {BOUND}"


def test_order_by_only_jql_gains_a_restriction() -> None:
    """A bare ORDER BY is rejected by Jira as unbounded; the window bounds it."""
    result = apply_cursor_to_jql("ORDER BY created DESC", CURSOR)
    assert result == f"{BOUND} ORDER BY created DESC"


def test_none_jql_yields_only_the_window() -> None:
    assert apply_cursor_to_jql(None, CURSOR) == BOUND


def test_none_jql_stays_none_on_full_resync() -> None:
    assert apply_cursor_to_jql(None, None) is None


def test_empty_jql_yields_only_the_window() -> None:
    """A bare epoch bound is a legal bounded query on search and both backlog paths."""
    assert apply_cursor_to_jql("", CURSOR) == BOUND


def test_configured_time_clause_caps_the_cursor_window() -> None:
    """The window intersects the configured JQL, it does not replace it."""
    result = apply_cursor_to_jql("created >= -1w AND project = FOO", CURSOR)
    assert result == f"(created >= -1w AND project = FOO) AND {BOUND}"


def test_cursor_in_the_future_falls_back_to_a_full_scope_run() -> None:
    """A future cursor is corrupt state; narrowing on it would skip real changes."""
    cursor = datetime.now(timezone.utc) + timedelta(minutes=10)
    assert apply_cursor_to_jql("project = TEST", cursor) == "project = TEST"
