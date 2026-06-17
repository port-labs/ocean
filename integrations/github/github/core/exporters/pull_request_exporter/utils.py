from datetime import UTC, datetime
from typing import Any, AsyncIterator, Callable, Optional

from loguru import logger


def filter_prs_by_date(
    prs: list[dict[str, Any]], date_field: str, cutoff: datetime
) -> list[dict[str, Any]]:

    return [
        pr
        for pr in prs
        if (
            (value := pr.get(date_field))
            and datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            >= cutoff
        )
    ]


async def paginate_closed_pull_requests(
    pages: AsyncIterator[list[dict[str, Any]]],
    *,
    enrich: Callable[[dict[str, Any]], dict[str, Any]],
    max_results: Optional[int],
    cutoff: Optional[datetime],
    include_field: str,
    stop_field: str,
    log_prefix: str,
    repo_name: str,
    organization: str,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Paginate closed pull requests for both the REST and GraphQL exporters.

    Each page is filtered by ``include_field`` against ``cutoff`` and capped to
    ``max_results`` (counting in-window PRs); pagination stops at the cutoff via
    ``stop_field``.
    """
    if cutoff is None:
        raise ValueError("paginate_closed_pull_requests requires a cutoff")

    total_count = 0
    async for page in pages:
        if not page:
            logger.info(
                f"{log_prefix} No more closed pull requests returned for repository "
                f"{repo_name} from {organization}; stopping."
            )
            break

        in_window = filter_prs_by_date(page, include_field, cutoff)
        if max_results is not None:
            remaining = max_results - total_count
            if remaining <= 0:
                break
            in_window = in_window[:remaining]

        batch = [enrich(pr) for pr in in_window]
        if batch:
            logger.info(
                f"{log_prefix} Fetched closed pull requests batch of {len(batch)} "
                f"from {repo_name} from {organization} "
                f"(total so far: {total_count + len(in_window)})"
            )
            yield batch
        total_count += len(in_window)

        # pages are sorted by stop_field desc and closed_at <= updated_at, so once the
        # last item predates the cutoff no later page can hold an in-window PR.
        if not filter_prs_by_date(page[-1:], stop_field, cutoff):
            logger.info(
                f"{log_prefix} Reached cutoff for closed pull requests of "
                f"{repo_name} from {organization}; stopping."
            )
            break

    logger.info(
        f"{log_prefix} Fetched total of {total_count} closed pull requests "
        f"from {organization}/{repo_name}"
    )
