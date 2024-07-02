from itertools import chain
from typing import Any


def flatten_list(lst: list[Any]) -> list[Any]:
    return list(chain.from_iterable(lst))


def split_list_into_batches(lst: list[Any], batch_size: int) -> list[list[Any]]:
    return [lst[i : i + batch_size] for i in range(0, len(lst), batch_size)]


def merge_and_batch(lists: list[Any], batch_size: int) -> list[list[Any]]:
    return split_list_into_batches(flatten_list(lists), batch_size)
