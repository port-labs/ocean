import asyncio
import dateutil.parser as dt_parser
import json
import yaml
from pathlib import Path
from loguru import logger
from gitlab.v4.objects import Project
from core.async_fetcher import AsyncFetcher
import jq

FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"
JSON_SUFFIX = ".json"

async def parse_datetime(datetime_str: str) -> str:
    obj = dt_parser.parse(datetime_str)
    return obj.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

async def generate_entity_from_port_yaml(
    raw_entity: dict, project: Project, ref: str, mappings: dict
) -> dict:
    properties = {}
    relations = {}

    for key, value in mappings["properties"].items():
        if isinstance(value, str) and value.startswith(FILE_PROPERTY_PREFIX):
            file_meta = Path(value.replace(FILE_PROPERTY_PREFIX, ""))
            gitlab_file = await AsyncFetcher.fetch_single(
                project.files.get, str(file_meta), ref
            )

            if file_meta.suffix == JSON_SUFFIX:
                properties[key] = json.loads(gitlab_file.decode("utf-8"))
            else:
                properties[key] = gitlab_file.decode("utf-8")
        else:
            properties[key] = jq.compile(value).input(raw_entity["properties"]).first()

    if "relations" in mappings:
        for key, value in mappings["relations"].items():
            relations[key] = jq.compile(value).input(raw_entity["properties"]).first()

    return {
        **raw_entity,
        "properties": properties,
        "relations": relations,
    }

def load_mappings(config_path: str) -> dict:
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return {resource["kind"]: resource["port"]["entity"]["mappings"] for resource in config["resources"]}