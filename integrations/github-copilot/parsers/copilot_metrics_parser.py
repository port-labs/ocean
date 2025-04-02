from typing import Any

def parse(metrics: list[dict[str, Any]], teamSlug: str, organization: str) -> list[dict[Any, Any]]:
    for metric in metrics:
        metric["team"] = teamSlug
        metric["org"] = organization
    return metrics
