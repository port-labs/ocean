import pickle
import os
from typing import Any


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
            pickle.dump(object, f)

    def load(self) -> Any:
        if not os.path.exists(self.file_path):
            return self.default_return
        with open(self.file_path, "rb") as f:
            return pickle.load(f)

    def delete(self) -> None:
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
