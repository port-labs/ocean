from typing import Any, Optional
from pydantic import BaseModel, Field, validator


class RepoSearchParams(BaseModel):
    query: str = Field(default_factory=str)
    operators: Optional[dict[str, Any]] = None

    _parsed_query: Optional[str] = None

    @validator("operators")
    def check_operator_validity(cls, value: Optional[dict[str, Any]]):
        valid_operators = {"archived", "forks"}
        if value is not None:
            operator_keys = set(value.keys())
            if valid_operators.issubset(operator_keys):
                raise ValueError(
                    f"unsupported search operators: {operator_keys.difference(valid_operators)}"
                )

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
