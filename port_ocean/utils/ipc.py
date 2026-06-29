import pickle
import os
from typing import Any

from loguru import logger


class FileIPC:
    def __init__(self, process_id: str, name: str, default_return: Any = None):
        self.process_id = process_id
        self.name = name
        self.dir_path = f"/tmp/ocean/processes/p_{self.process_id}"
        self.file_path = f"{self.dir_path}/{self.name}.pkl"
        self.default_return = default_return
        os.makedirs(self.dir_path, exist_ok=True)

    def __del__(self) -> None:
        self.delete()

    def save(self, object: Any) -> None:
        with open(self.file_path, "wb") as f:
            pickle.dump(object, f)  # type: ignore[arg-type]

    def load(self) -> Any:
        if not os.path.exists(self.file_path):
            return self.default_return
        with open(self.file_path, "rb") as f:
            return pickle.load(f)

    def append_batch(self, batch: list[Any]) -> None:
        """Append a batch to the file without loading the full contents into memory."""
        with open(self.file_path, "ab") as f:
            pickle.dump(batch, f)  # type: ignore[arg-type]

    def load_all_batches(self) -> list[Any]:
        """Load all batches appended via append_batch and return a single flat list."""
        if not os.path.exists(self.file_path):
            return []
        result: list[Any] = []
        with open(self.file_path, "rb") as f:
            while True:
                try:
                    result.extend(pickle.load(f))
                except EOFError:
                    break
                except pickle.UnpicklingError:
                    logger.warning(
                        f"Encountered a corrupt pickle frame while reading entity batches from {self.file_path} — subprocess may have been killed mid-write. Returning partial results."
                    )
                    break
        return result

    def delete(self) -> None:
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
