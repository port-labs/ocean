import re
from datetime import datetime, timezone

from loguru import logger

_ORDER_BY_PATTERN = re.compile(r"\border\s+by\b", re.IGNORECASE)
_QUOTED_PATTERN = re.compile(r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'")


def _split_order_by(jql: str) -> tuple[str, str]:
    """Split ``jql`` into its filter clauses and its trailing ``ORDER BY``.

    Quoted literals are masked before the search so an ``order by`` inside a
    value is not read as the clause. The mask consumes backslash escapes, so a
    literal holding an escaped quote still masks as one unit.
    """
    masked = _QUOTED_PATTERN.sub(lambda match: "_" * len(match.group()), jql)
    match = _ORDER_BY_PATTERN.search(masked)
    if not match:
        return jql.strip(), ""
    return jql[: match.start()].strip(), jql[match.start() :].strip()


def _as_utc(value: datetime) -> datetime:
    """Normalise a cursor whose type does not promise an offset.

    The cursor API stores the timestamp string verbatim — a naive value written
    by anything other than core is handed back naive — and ``timestamp()`` would
    read that as container-local. Mirrors the private
    ``port_ocean.utils.relative_time._as_utc``.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _window_from_cursor(cursor: datetime) -> str:
    """Build the ``updated`` lower bound for ``cursor``.

    The bound is unquoted epoch milliseconds, which JQL reads as an instant:
    "if you omit the quote-marks, the number you supply will be interpreted as
    milliseconds after epoch (1970-1-1)". A quoted literal has no offset form
    and resolves in the searching user's time zone, so it would need that zone
    fetched per sync and the value floored to the minute literals carry.
    https://support.atlassian.com/jira-software-cloud/docs/jql-fields/
    """
    return f"updated >= {int(cursor.timestamp() * 1000)}"


def apply_cursor_to_jql(jql: str | None, cursor: datetime | None) -> str | None:
    """Narrow ``jql`` to issues updated since ``cursor``.

    The window intersects the configured JQL rather than replacing it, so an
    incremental run always returns a subset of what a full resync returns;
    free-form JQL cannot be stripped of its own time clauses the way a typed
    selector field can, so a configured clause also caps the window.

    The bound is absolute rather than the relative ``-Nm`` syntax, because Jira
    re-evaluates the JQL on every page request and a relative bound walks
    forward mid-run, dropping issues from later pages.

    Search is eventually consistent, and the bound carries no margin for it:
    measured lag was below the HTTP round trip (under 1.5s for 5/5 issues), and
    a change missed by that much is picked up by the scheduled full resync. The
    documented remedy is ``reconcileIssues``, which does not fit a window query
    anyway — it reconciles up to 50 named issue ids, and a window does not know
    which ids it is waiting for.
    https://developer.atlassian.com/cloud/jira/platform/search-and-reconcile/
    """
    if cursor is None:
        return jql

    cursor = _as_utc(cursor)
    now = datetime.now(timezone.utc)
    if cursor > now:
        logger.warning(
            f"Incremental cursor {cursor.isoformat()} is ahead of now "
            f"({now.isoformat()}); resyncing the full configured scope"
        )
        return jql

    window = _window_from_cursor(cursor)
    if not jql:
        return window

    filters, ordering = _split_order_by(jql)
    clause = f"({filters}) AND {window}" if filters else window
    return f"{clause} {ordering}".strip()
