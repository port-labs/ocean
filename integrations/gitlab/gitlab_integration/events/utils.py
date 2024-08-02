from typing import Any, Dict


def remove_prefix_from_keys(prefix: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Removes the prefix from dictionary keys.
    Args:
        prefix (str): The prefix to remove from the keys
        data (dict[str, Any]): The original dictionary with keys that may start with the given prefix.
    Returns:
        dict[str, Any]: A new dictionary with `prefix` stripped from the keys.
    """
    return {key.replace(prefix, "", 1): value for key, value in data.items()}
