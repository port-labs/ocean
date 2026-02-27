from typing import Literal, TypedDict


class ListRepositoriesOptions(TypedDict):
    include_inactive: bool


class ListContainersOptions(TypedDict):
    filter_status: Literal["all", "active", "inactive"]
