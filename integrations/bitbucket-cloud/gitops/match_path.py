import fnmatch
from typing import Union, List

PORT_CONFIG_FILES = ("port.yml", "port.yaml")


def match_spec_paths(file_path: str, spec_paths: Union[str, List[str]]) -> List[str]:
    if isinstance(spec_paths, list):
        matching_paths = []
        for spec_path in spec_paths:
            if _is_matching_path(file_path, spec_path):
                matching_paths.append(file_path)
        return matching_paths
    return [file_path] if _is_matching_path(file_path, spec_paths) else []


def _is_matching_path(file_path: str, spec_path: str) -> bool:
    return (
        fnmatch.fnmatch(file_path, spec_path)
        or fnmatch.fnmatch(file_path, spec_path.replace("**/", ""))
    ) and file_path.endswith(PORT_CONFIG_FILES)
