#!/usr/bin/env python3
"""Local HTTP fixtures for Custom Ocean pagination e2e (relative next_link + body cursor)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import uvicorn
from fastapi import Body, FastAPI

RELATIVE_NEXT_LINK_ITEMS = "/pagination/relative-next/items"
BODY_CURSOR_QUERY = "/pagination/body-cursor/query"

_RELATIVE_PAGES: Dict[Optional[str], Dict[str, Any]] = {
    None: {
        "results": [
            {"id": "rel-1", "name": "Relative Page One"},
            {"id": "rel-1b", "name": "Relative Page One B"},
        ],
        "_links": {"next": f"{RELATIVE_NEXT_LINK_ITEMS}?cursor=page-2"},
    },
    "page-2": {
        "results": [
            {"id": "rel-2", "name": "Relative Page Two"},
            {"id": "rel-2b", "name": "Relative Page Two B"},
        ],
    },
}

_BODY_CURSOR_PAGES: Dict[Optional[str], Dict[str, Any]] = {
    None: {
        "data": [
            {"id": "body-1", "name": "Body Cursor Page One"},
            {"id": "body-1b", "name": "Body Cursor Page One B"},
        ],
        "next_page_token": "body-page-2",
        "has_more": True,
    },
    "body-page-2": {
        "data": [
            {"id": "body-2", "name": "Body Cursor Page Two"},
            {"id": "body-2b", "name": "Body Cursor Page Two B"},
        ],
        "has_more": False,
    },
}

app = FastAPI(title="custom-ocean-pagination-fixtures")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get(RELATIVE_NEXT_LINK_ITEMS)
async def relative_next_items(cursor: Optional[str] = None) -> Dict[str, Any]:
    return _RELATIVE_PAGES.get(cursor, _RELATIVE_PAGES[None])


@app.post(BODY_CURSOR_QUERY)
async def body_cursor_query(
    payload: Dict[str, Any] = Body(default_factory=dict),
) -> Dict[str, Any]:
    token = payload.get("next_page_token")
    return _BODY_CURSOR_PAGES.get(token, _BODY_CURSOR_PAGES[None])


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
