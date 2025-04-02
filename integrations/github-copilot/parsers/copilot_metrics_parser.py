from typing import Any

def parse(metrics: list[dict[str, Any]], teamSlug: str, organization: str) -> list[dict[Any, Any]]:
    parsed_data = []
    for metric in metrics:
        metric["team"] = teamSlug
        metric["org"] = organization
        parsed_data.append(metric)
    return parsed_data
