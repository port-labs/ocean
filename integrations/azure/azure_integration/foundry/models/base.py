from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class FoundryModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(**{**kwargs, "exclude_none": True, "by_alias": True})
