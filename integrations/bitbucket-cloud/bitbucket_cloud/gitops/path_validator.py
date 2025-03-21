import fnmatch
from typing import Union, List

PORT_CONFIG_FILES = ("port.yml", "port.yaml")


def match_spec_paths(
    file_path: str, target_path: str, spec_paths: Union[str, List[str]]
) -> List[str]:
    matching_paths = []
    if isinstance(spec_paths, list):
        for spec_path in spec_paths:
            if match_path_pattern(file_path, spec_path):
                matching_paths.append(file_path)
            elif match_path_pattern(target_path, spec_path):
                matching_paths.append(target_path)
    else:
        if match_path_pattern(file_path, spec_paths):
            matching_paths.append(file_path)
        if match_path_pattern(target_path, spec_paths):
            matching_paths.append(target_path)
    return matching_paths


def match_path_pattern(file_path: str, spec_path: str) -> bool:
    return (
        fnmatch.fnmatch(file_path, spec_path)
        or fnmatch.fnmatch(file_path, spec_path.replace("**/", ""))
    ) and file_path.endswith(PORT_CONFIG_FILES)
