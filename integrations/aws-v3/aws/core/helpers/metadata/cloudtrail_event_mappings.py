from aws.core.exporters.exporter_metadata import kind_to_export_metadata
from aws.core.helpers.metadata.types import EventNameMapping


def cloudtrail_mapping_key(event_name: str, event_source: str | None = None) -> str:
    if event_source:
        return f"{event_source}:{event_name}"
    return event_name


def build_event_name_mappings() -> dict[str, EventNameMapping]:
    mappings: dict[str, EventNameMapping] = {}
    for kind, metadata in kind_to_export_metadata.items():
        if metadata.live_events is None:
            continue
        for event_name, mapping in metadata.live_events.cloudtrail_mappings.items():
            key = cloudtrail_mapping_key(event_name, mapping.event_source)
            mappings[key] = EventNameMapping(
                kind=kind,
                action=mapping.action,
                extract_identifier=mapping.extract_identifier,
            )
    return mappings


EVENT_NAME_MAPPINGS = build_event_name_mappings()
