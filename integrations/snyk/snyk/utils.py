from typing import Any, Optional


def enrich_batch_with_org(
    batch: list[dict[str, Any]],
    enrichment_data: Any,
    enricment_key: str = "__organization",
) -> list[dict[str, Any]]:
    for item in batch:
        item[enricment_key] = enrichment_data

    return batch


def get_matching_organization(
    orgs: list[dict[str, Any]], org_id: str
) -> Optional[dict[str, Any]]:
    for org in orgs:
        if org["id"] == org_id:
            return org
