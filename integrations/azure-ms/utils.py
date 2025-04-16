from typing import Generator, TypeVar

T = TypeVar("T")


def turn_sequence_to_chunks(
    sequence: list[T], chunk_size: int
) -> Generator[list[T], None, None]:
    if chunk_size >= len(sequence):
        yield sequence
        return

    start, end = 0, chunk_size

    while start <= len(sequence) and sequence[start:end]:
        yield sequence[start:end]
        start += chunk_size
        end += chunk_size

    return
