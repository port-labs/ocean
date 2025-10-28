from typing import Any, Optional
from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr, validator


class RepoSearchParams(BaseModel):
    query: str = Field(default_factory=str)
    operators: Optional[dict[str, Any]] = Field(default=None)

    _parsed_query: Optional[str] = PrivateAttr(default=None)

    @validator("operators")
    def check_operator_validity(cls, value: Optional[dict[str, Any]]):
        valid_operators = {"archived", "forks"}
        if value is not None:
            operator_keys = set(value.keys())
            if not valid_operators.issuperset(operator_keys):
                logger.warning(
                    "invalid search operators",
                    operator_keys.difference(valid_operators),
                )
                raise ValueError(
                    f"unsupported search operators: {operator_keys.difference(valid_operators)}"
                )

        return value

    @property
    def search_query(self) -> str:
        if self._parsed_query is not None:
            return self._parsed_query

        if self.operators is None:
            self._parsed_query = self.query
            return self._parsed_query

        parsed_operators = " ".join(
            f"{key}:{value}" for key, value in self.operators.items()
        )
        self._parsed_query = f"{self.query}{parsed_operators}"
        return self._parsed_query
