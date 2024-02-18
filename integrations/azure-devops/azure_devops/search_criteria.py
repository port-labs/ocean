from datetime import datetime, timedelta
from typing import Any


PULL_REQUEST_SEARCH_CRITERIA: list[dict[str, Any]] = [
    {"searchCriteria.status": "active"},
    {
        "searchCriteria.status": "all",
        "searchCriteria.maxTime": datetime.now() - timedelta(days=30),
    },
]

MAX_WORK_ITEMS_PER_QUERY = 400
WORK_ITEMS_WIQL_QUERY = "select * from workitems"
