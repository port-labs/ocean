from enum import StrEnum
from random import randint
from typing import Callable, List, Dict, Any, AsyncGenerator

from loguru import logger
import yaml

from port_ocean.utils import http_async_client

from fake_org_data.types import FakeIntegrationConfig, FakeSelector
from .types import FakePerson
from .static import FAKE_DEPARTMENTS


API_URL = "http://localhost:9000/fake-integration"
USER_AGENT = "Ocean Framework Fake Integration (https://github.com/port-labs/ocean)"


class FakeIntegrationConfigKeys(StrEnum):
    ENTITY_AMOUNT = "entity_amount"
    ENTITY_KB_SIZE = "entity_kb_size"
    THIRD_PARTY_BATCH_SIZE = "third_party_batch_size"
    THIRD_PARTY_LATENCY_MS = "third_party_latency_ms"
    SINGLE_PERF_RUN = "single_department_run"


def get_config(fake_selector: FakeSelector) -> FakeIntegrationConfig:
    return FakeIntegrationConfig(**fake_selector.dict(by_alias=True))


async def get_fake_persons(config: FakeIntegrationConfig) -> List[Dict[Any, Any]]:
    url = f"{API_URL}/fake-employees?entity_amount={config.entity_count}&entity_kb_size={config.entity_size_kb}&latency={config.delay_ms}&items_to_parse_entity_count={config.items_to_parse_entity_count}&items_to_parse_entity_size_kb={config.items_to_parse_entity_size_kb}"
    response = await http_async_client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    raw_persons = response.json()

    return [
        FakePerson(**{**person}).dict() for person in raw_persons.get("results", [])
    ]


def get_random_department_id() -> str:
    return FAKE_DEPARTMENTS[randint(0, len(FAKE_DEPARTMENTS) - 1)].id


async def get_departments(config: FakeIntegrationConfig) -> List[Dict[Any, Any]]:
    return [department.dict() for department in FAKE_DEPARTMENTS]


async def get_fake_readme_file(config: FakeIntegrationConfig) -> str:
    url = f"{API_URL}/fake-file/{config.file_path}?file_size_kb={config.file_size_kb}&latency={config.delay_ms}"
    response = await http_async_client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    raw_content = response.json()
    return raw_content.get("content", "")


async def get_fake_codeowners_file(
    config: FakeIntegrationConfig,
) -> List[Dict[str, Any]]:
    url = f"{API_URL}/fake-file/{config.file_path}?row_count={config.codeowners_row_count}&latency={config.delay_ms}"
    response = await http_async_client.get(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    content = response.json().get("content", "")
    # Wrap string content in a list with a dict wrapper to match expected format
    if isinstance(content, str):
        return [{"content": content}]
    return content if isinstance(content, list) else [content]


def handle_yaml_file(raw_content: str) -> Dict[str, Any]:
    try:
        parsed = yaml.safe_load(raw_content)
        return parsed if parsed is not None else {}
    except yaml.YAMLError:
        raise ValueError(f"Failed to parse YAML file: {raw_content}")


async def get_fake_yaml_file(config: FakeIntegrationConfig) -> List[Dict[str, Any]]:
    url = f"{API_URL}/fake-file/{config.file_path}?entity_amount={config.entity_count}&entity_kb_size={config.entity_size_kb}&items_to_parse_entity_count={config.items_to_parse_entity_count}&items_to_parse_entity_size_kb={config.items_to_parse_entity_size_kb}&latency={config.delay_ms}"
    response = await http_async_client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    raw_content = response.json()
    content_str = raw_content["content"]
    # Handle YAML content - it might be a string that needs parsing
    if isinstance(content_str, str):
        parsed = handle_yaml_file(content_str)
        return parsed if isinstance(parsed, list) else [parsed]
    if isinstance(content_str, list):
        return content_str
    return (
        [content_str] if isinstance(content_str, dict) else [{"content": content_str}]
    )


async def get_fake_json_file(config: FakeIntegrationConfig) -> List[Dict[str, Any]]:
    url = f"{API_URL}/fake-file/{config.file_path}?entity_amount={config.entity_count}&entity_kb_size={config.entity_size_kb}&items_to_parse_entity_count={config.items_to_parse_entity_count}&items_to_parse_entity_size_kb={config.items_to_parse_entity_size_kb}&latency={config.delay_ms}"
    response = await http_async_client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    raw_content = response.json()
    # Parse JSON string if needed
    logger.debug(
        f"Received response for JSON file, content type: {type(raw_content.get('content'))}"
    )
    content = raw_content.get("content", "")

    import json
    import base64

    try:
        decoded_content = base64.b64decode(content).decode("utf-8")
        content = json.loads(decoded_content)
        logger.debug(
            f"Successfully decoded base64 and parsed JSON, got {type(content)}"
        )
    except Exception as e:
        logger.error(f"Failed to parse content as JSON: {e}")
        raise ValueError(f"Failed to parse content as JSON: {e}")

    return content


async def get_fake_repositories(config: FakeIntegrationConfig) -> List[Dict[Any, Any]]:
    url = f"{API_URL}/fake-repositories?entity_amount={config.entity_count}&entity_kb_size={config.entity_size_kb}&latency={config.delay_ms}"
    response = await http_async_client.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    raw_repos = response.json()
    return raw_repos.get("results", [])


async def invoke_fake_webhook_event(
    config: FakeIntegrationConfig,
) -> List[Dict[Any, Any]]:
    url = f"{API_URL}/fake-webhook?entity_amount={config.entity_count}&entity_kb_size={config.entity_size_kb}&latency={config.delay_ms}&items_to_parse_entity_count={config.items_to_parse_entity_count}&items_to_parse_entity_size_kb={config.items_to_parse_entity_size_kb}&webhook_action={config.webhook_action}"
    response = await http_async_client.post(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    return response.json()


async def get_in_batches(
    config: FakeSelector, func: Callable[[FakeIntegrationConfig], Any]
) -> AsyncGenerator[List[Dict[Any, Any]], None]:
    config = get_config(config)
    for batch_num in range(config.batch_count):
        try:
            result = await func(config)
            # Ensure result is a list
            if not isinstance(result, list):
                logger.warning(
                    f"Function returned non-list type {type(result)}, skipping batch {batch_num + 1}"
                )
                continue
            # Skip empty batches to avoid processing issues
            if len(result) == 0:
                logger.debug(f"Batch {batch_num + 1} is empty, skipping")
                continue
            logger.debug(f"Yielding batch {batch_num + 1} with {len(result)} items")
            yield result
        except Exception as e:
            logger.error(f"Error in batch {batch_num + 1}: {e}", exc_info=True)
            # Continue to next batch instead of failing completely
            continue
