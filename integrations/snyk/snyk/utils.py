from typing import Any


def enrich_batch_with_org(
    batch: list[dict[str, Any]],
    enrichment_data: Any,
    enricment_key: str = "__organization",
) -> list[dict[str, Any]]:
    for item in batch:
        item[enricment_key] = enrichment_data

    return batch
