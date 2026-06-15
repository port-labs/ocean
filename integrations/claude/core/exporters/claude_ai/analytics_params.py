from typing import Any

from core.options import ListUserReportOptions

# Maps the option key (snake_case) to the Anthropic repeated array query param.
_ARRAY_PARAM_KEYS = {
    "products": "products[]",
    "models": "models[]",
    "group_by": "group_by[]",
    "context_windows": "context_windows[]",
    "inference_geos": "inference_geos[]",
    "speeds": "speeds[]",
}


def build_analytics_query_params(options: ListUserReportOptions) -> dict[str, Any]:
    """Translate shared Claude AI report options into query parameters."""
    params: dict[str, Any] = {
        "starting_at": options["starting_at"],
        "ending_at": options["ending_at"],
        "limit": options["limit"],
        "exclude_deleted_users": options.get("exclude_deleted_users", False),
    }

    for option_key, query_key in _ARRAY_PARAM_KEYS.items():
        values = options.get(option_key)
        if values:
            params[query_key] = values

    return params
