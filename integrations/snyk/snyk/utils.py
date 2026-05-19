from collections import defaultdict
from typing import Any, Optional

from httpx import URL


def parse_next_page_params(next_url: str) -> tuple[str, dict[str, Any]]:
    parsed = URL(next_url)
    url_path = parsed.raw_path.decode().replace("/rest", "")
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for k, v in parsed.params.multi_items():
        grouped[k].append(v)
    query_params: dict[str, Any] = {
        k: vs[0] if len(vs) == 1 else vs for k, vs in grouped.items()
    }
    return url_path, query_params


def enrich_batch_with_data(
    batch: list[dict[str, Any]],
    enrichment_data: Any,
    enrichment_key: str = "__organization",
) -> list[dict[str, Any]]:
    for item in batch:
        item[enrichment_key] = enrichment_data

    return batch


def get_matching_organization(
    orgs: list[dict[str, Any]], org_id: str
) -> Optional[dict[str, Any]]:
    for org in orgs:
        if org["id"] == org_id:
            return org

    return None
