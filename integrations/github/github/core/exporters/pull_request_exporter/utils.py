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
    updated_after: Optional[datetime],
    closed_after: Optional[datetime],
    updated_at_field: str,
    closed_at_field: str,
    log_prefix: str,
    repo_name: str,
    organization: str,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Paginate closed pull requests for both the REST and GraphQL exporters.

    Exactly one cutoff selects the mode:
    - ``closed_after`` set: filter each page by ``closed_at`` then cap to ``max_results``
      (cap counts in-window PRs); stop once a page holds a PR updated before the cutoff.
    - ``updated_after`` set: cap the raw page to ``max_results`` (cap counts scanned PRs)
      then filter by ``updated_at``; pagination runs until ``max_results`` is reached.
    """

    close_mode = closed_after is not None
    cutoff = closed_after if close_mode else updated_after
    if cutoff is None:
        raise ValueError(
            "paginate_closed_pull_requests requires either updated_after or closed_after"
        )

    total_count = 0
    async for page in pages:
        if not page:
            logger.info(
                f"{log_prefix} No more closed pull requests returned for repository "
                f"{repo_name} from {organization}; stopping."
            )
            break

        if close_mode:
            in_window = filter_prs_by_date(page, closed_at_field, cutoff)
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

            # closed_at <= updated_at and results are sorted by updated_at desc, so once
            # updated_at falls before the cutoff no later page can hold an in-window PR.
            if len(filter_prs_by_date(page, updated_at_field, cutoff)) < len(page):
                logger.info(
                    f"{log_prefix} Reached cutoff for closed pull requests of "
                    f"{repo_name} from {organization}; stopping."
                )
                break
        else:
            if max_results is not None:
                remaining = max_results - total_count
                if remaining <= 0:
                    break
                raw = page[:remaining]
            else:
                raw = page
            raw_count = len(raw)
            logger.info(
                f"{log_prefix} Fetched closed pull requests batch of {raw_count} "
                f"from {repo_name} from {organization} "
                f"(total so far: {total_count + raw_count}/{max_results})"
            )
            yield [
                enrich(pr) for pr in filter_prs_by_date(raw, updated_at_field, cutoff)
            ]
            total_count += raw_count

    logger.info(
        f"{log_prefix} Fetched total of {total_count} closed pull requests "
        f"from {organization}/{repo_name}"
    )
