from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from core.utils import parse_datetime, generate_entity_from_port_yaml, load_mappings
import pytest
from gitlab.v4.objects import Project
from pathlib import Path
import json
import yaml
import jq

@pytest.mark.asyncio
async def test_parse_datetime():
    datetime_str = "2023-10-01T12:34:56Z"
    result = await parse_datetime(datetime_str)

    assert result == "2023-10-01T12:34:56.000000Z"

@pytest.mark.asyncio
@patch('core.async_fetcher.AsyncFetcher.fetch_single')
async def test_generate_entity_from_port_yaml(mock_fetch_single):
    raw_entity = {
        "properties": {
            "createdAt": "2023-10-01T12:34:56Z",
            "updatedAt": "2023-10-01T12:34:56Z",
            "serviceName": "mock_service"
        }
    }
    project = MagicMock(spec=Project)
    project.files = MagicMock()  # Ensure the project object has the files attribute
    ref = "main"
    mappings = {
        "identifier": ".serviceName",
        "title": ".serviceName",
        "blueprint": "project",
        "properties": {
            "serviceName": "file://path/to/file.json",
            "createdAt": ".createdAt",
            "updatedAt": ".updatedAt"
        },
        "relations": {
            "service": ".serviceName"
        }
    }
    mock_file_content = b'{"serviceName": "mock_service"}'
    mock_fetch_single.return_value = mock_file_content

    result = await generate_entity_from_port_yaml(raw_entity, project, ref, mappings)

    mock_fetch_single.assert_called_once_with(project.files.get, "path/to/file.json", ref)
    assert result == {
        "identifier": jq.compile(mappings["identifier"]).input(raw_entity["properties"]).first(),
        "title": jq.compile(mappings["title"]).input(raw_entity["properties"]).first(),
        "blueprint": mappings["blueprint"],
        "properties": {
            "serviceName": {"serviceName": "mock_service"},
            "createdAt": "2023-10-01T12:34:56.000000Z",
            "updatedAt": "2023-10-01T12:34:56.000000Z"
        },
        "relations": {
            "service": "mock_service"
        }
    }

def test_load_mappings():
    config_path = ".port/resource/port-app-config.yml"
    mock_config = {
        "resources": [
            {
                "kind": "project",
                "port": {
                    "entity": {
                        "mappings": {
                            "properties": {
                                "name": ".name",
                                "description": ".description"
                            }
                        }
                    }
                }
            },
            {
                "kind": "group",
                "port": {
                    "entity": {
                        "mappings": {
                            "properties": {
                                "name": ".name",
                                "path": ".path"
                            }
                        }
                    }
                }
            }
        ]
    }
    with patch('builtins.open', return_value=MagicMock(read=MagicMock(return_value=yaml.dump(mock_config)))) as mock_open:
        mappings = load_mappings(config_path)

        mock_open.assert_called_once_with(config_path, "r")
        assert mappings == {
            "project": {
                "properties": {
                    "name": ".name",
                    "description": ".description"
                }
            },
            "group": {
                "properties": {
                    "name": ".name",
                    "path": ".path"
                }
            }
        }
