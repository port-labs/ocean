from typing import Any

import pytest

from client import turn_sequence_to_chunks


@pytest.mark.parametrize(
    "input, output, chunk_size",
    [
        ([1, 2, 4], [[1], [2], [4]], 1),
        ([1, 2, 4], [[1, 2], [4]], 2),
        ([1, 2, 3, 4, 5, 6, 7], [[1, 2, 3, 4, 5, 6, 7]], 7),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]], 2),
    ],
)
def test_turn_sequence_to_chunks(
    input: list[Any], output: list[list[Any]], chunk_size: int
) -> None:
    assert list(turn_sequence_to_chunks(input, chunk_size)) == output
