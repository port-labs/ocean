import fnmatch
from typing import Union, List

PORT_CONFIG_FILES = ("port.yml", "port.yaml")


def match_spec_paths(
    file_path: str, target_path: str, spec_paths: Union[str, List[str]]
) -> List[str]:
    matching_paths = []
    if isinstance(spec_paths, list):
        for spec_path in spec_paths:
            if _is_matching_path(file_path, spec_path):
                matching_paths.append(file_path)
            elif _is_matching_path(target_path, spec_path):
                matching_paths.append(target_path)
        return matching_paths
    else:
        if _is_matching_path(file_path, spec_paths):
            matching_paths.append(file_path)
        if _is_matching_path(target_path, spec_paths):
            matching_paths.append(target_path)
        return matching_paths


def _is_matching_path(file_path: str, spec_path: str) -> bool:
    return (
        fnmatch.fnmatch(file_path, spec_path)
        or fnmatch.fnmatch(file_path, spec_path.replace("**/", ""))
    ) and file_path.endswith(PORT_CONFIG_FILES)
