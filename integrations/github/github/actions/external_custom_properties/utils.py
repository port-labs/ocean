from typing import Any


def external_custom_properties_from_mapping(
    external_properties_mapping: dict[str, Any],
) -> list[dict[str, str | None]]:
    return [
        {
            "property_name": name,
            "value": None if value is None or value == "" else str(value),
        }
        for name, value in external_properties_mapping.items()
    ]
