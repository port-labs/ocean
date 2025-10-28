from typing import Any, Optional
from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr, validator


class RepoSearchParams(BaseModel):
    query: str = Field(default_factory=str)
    operators: Optional[dict[str, Any]] = Field(default=None)

    _parsed_query: Optional[str] = PrivateAttr(default=None)

    @validator("operators")
    def check_operator_validity(
        cls, value: Optional[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """
        Checks if the provided search operators are valid and removes the invalid ones.

        If any of the operators are not in the `valid_operators` set, a warning is logged
        and the invalid operators are removed from the dictionary.

        ref: https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories
        """
        valid_operators = {"archived", "fork", "is", "forks", "stars", "size"}
        if value is not None:
            operator_keys = set(value.keys())
            if not valid_operators.issuperset(operator_keys):
                bad_search_operators = operator_keys.difference(valid_operators)
                logger.warning(
                    f"unsupported search operators: {', '.join(bad_search_operators)}. these will be excluded from search query "
                )
                for key in bad_search_operators:
                    del value[key]

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
