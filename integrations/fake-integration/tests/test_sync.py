import os
import inspect
from typing import Any, AsyncGenerator, Dict, List
from port_ocean.tests.helpers.ocean_app import (
    get_raw_result_on_integration_sync_resource_config,
)
from pytest_httpx import HTTPXMock
import pytest

from fake_org_data import fake_client
from fake_org_data.types import (
    FakeDepartment,
    FakePerson,
    FakePersonStatus,
    FakeProject,
)
from webhook_processors import (
    FakePersonWebhookProcessor,
    FakeDepartmentWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    MappingsConfig,
    EntityMapping,
)

USER_AGENT = "Ocean Framework Fake Integration (https://github.com/port-labs/ocean)"

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

FAKE_PERSON = FakePerson(
    id="ZOMG",
    email="test@zomg.io",
    age=42,
    name="Joe McToast",
    bio="ZOMG I've been endorsed for xml!",
    status=FakePersonStatus.NOPE,
    department=FakeDepartment(id="hr", name="hr"),
    projects=[
        FakeProject(id="proj-1", name="Test Project 1", status="active"),
        FakeProject(id="proj-2", name="Test Project 2", status="completed"),
    ],
)

FAKE_PERSON_RAW = FAKE_PERSON.dict()


async def assert_on_results(results: Any, kind: str) -> None:
    assert len(results) > 0
    resync_results, errors = results
    if inspect.isasyncgen(resync_results[0]):
        async for entities in resync_results[0]:
            await assert_on_results((entities, errors), kind)
            return
    entities = resync_results
    assert len(entities) > 0
    if kind == "fake-person":
        assert entities[0] == FAKE_PERSON_RAW
    else:
        assert len(entities) == 5


async def test_full_sync_with_http_mock(
    get_mocked_ocean_app: Any,
    get_mock_ocean_resource_configs: Any,
    httpx_mock: HTTPXMock,
) -> None:
    return
    httpx_mock.add_response(
        match_headers={"User-Agent": USER_AGENT},
        json={
            "results": [
                FAKE_PERSON_RAW,
            ]
        },
    )

    app = get_mocked_ocean_app()
    resource_configs = get_mock_ocean_resource_configs()

    for resource_config in resource_configs:
        results = await get_raw_result_on_integration_sync_resource_config(
            app, resource_config
        )

        await assert_on_results(results, resource_config.kind)


async def mock_fake_person() -> AsyncGenerator[List[Dict[Any, Any]], None]:
    yield [FakePerson(**FAKE_PERSON_RAW).dict()]


async def test_full_sync_using_mocked_3rd_party(
    monkeypatch: Any,
    get_mocked_ocean_app: Any,
    get_mock_ocean_resource_configs: Any,
) -> None:
    monkeypatch.setattr(fake_client, "get_fake_persons", mock_fake_person)

    app = get_mocked_ocean_app()
    resource_configs = get_mock_ocean_resource_configs()

    for resource_config in resource_configs:
        results = await get_raw_result_on_integration_sync_resource_config(
            app, resource_config
        )

        await assert_on_results(results, resource_config.kind)


@pytest.mark.asyncio
async def test_items_to_parse_functionality(
    get_mocked_ocean_app: Any,
) -> None:
    """Test that itemsToParse correctly parses projects from fake-person entities"""
    app = get_mocked_ocean_app()

    # Create a resource config with itemsToParse for projects
    resource_config = ResourceConfig(
        kind="fake-person",
        selector=Selector(query=".projects != null and (.projects | length) > 0"),
        port=PortResourceConfig(
            itemsToParse=".projects",
            itemsToParseName="project",
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".project.id",
                    title=".project.name",
                    blueprint='"fake-project"',
                    properties={
                        "name": ".project.name",
                        "status": ".project.status",
                    },
                    relations={
                        "person": ".id",
                    },
                )
            ),
        ),
    )

    # Mock the resync function to return a person with projects
    async def mock_person_with_projects(
        kind: str,
    ) -> AsyncGenerator[List[Dict[Any, Any]], None]:
        yield [FAKE_PERSON_RAW]

    # Patch the resync handler
    import fake_org_data.fake_client as fake_client_module

    original_get_fake_persons = fake_client_module.get_fake_persons
    fake_client_module.get_fake_persons = mock_person_with_projects

    try:
        results = await get_raw_result_on_integration_sync_resource_config(
            app, resource_config
        )

        resync_results, errors = results
        entities = []

        # Collect all entities from async generator
        if inspect.isasyncgen(resync_results[0]):
            async for batch in resync_results[0]:
                entities.extend(batch)
        else:
            entities = resync_results

        # Verify that we got project entities (one per project)
        assert len(entities) == 2, f"Expected 2 project entities, got {len(entities)}"

        # Verify each entity has the project data merged
        for entity in entities:
            assert "project" in entity, "Entity should have 'project' key"
            assert "id" in entity, "Entity should have person 'id'"
            assert entity["project"]["id"] in ["proj-1", "proj-2"]
            assert entity["project"]["name"].startswith("Test Project")
    finally:
        # Restore original function
        fake_client_module.get_fake_persons = original_get_fake_persons


@pytest.mark.asyncio
async def test_fake_person_webhook_processor() -> None:
    """Test FakePersonWebhookProcessor methods"""
    # Create a mock event
    event = WebhookEvent(
        trace_id="test-trace",
        headers={},
        payload={"type": "person", "person_id": "test-123"},
    )

    processor = FakePersonWebhookProcessor(event)

    # Test authenticate
    assert await processor.authenticate({}, {}) is True

    # Test validate_payload
    assert await processor.validate_payload({"type": "person"}) is True
    assert await processor.validate_payload({"event": "create"}) is True
    assert await processor.validate_payload({}) is False

    # Test should_process_event
    assert await processor.should_process_event(event) is True

    event_department = WebhookEvent(
        trace_id="test-trace",
        headers={},
        payload={"type": "department"},
    )
    assert await processor.should_process_event(event_department) is False

    # Test get_matching_kinds
    kinds = await processor.get_matching_kinds(event)
    assert kinds == ["fake-person"]


@pytest.mark.asyncio
async def test_fake_department_webhook_processor() -> None:
    """Test FakeDepartmentWebhookProcessor methods"""
    # Create a mock event
    event = WebhookEvent(
        trace_id="test-trace",
        headers={},
        payload={"type": "department", "department_id": "dept-123"},
    )

    processor = FakeDepartmentWebhookProcessor(event)

    # Test authenticate
    assert await processor.authenticate({}, {}) is True

    # Test validate_payload
    assert await processor.validate_payload({"type": "department"}) is True
    assert await processor.validate_payload({"event": "create"}) is True
    assert await processor.validate_payload({}) is False

    # Test should_process_event
    assert await processor.should_process_event(event) is True

    event_person = WebhookEvent(
        trace_id="test-trace",
        headers={},
        payload={"type": "person"},
    )
    assert await processor.should_process_event(event_person) is False

    # Test get_matching_kinds
    kinds = await processor.get_matching_kinds(event)
    assert kinds == ["fake-department"]


@pytest.mark.asyncio
async def test_webhook_processor_handle_event_delete(
    monkeypatch: Any,
) -> None:
    """Test webhook processor handles delete events correctly"""
    event = WebhookEvent(
        trace_id="test-trace",
        headers={},
        payload={"type": "delete", "person_id": "person-123"},
    )

    processor = FakePersonWebhookProcessor(event)
    resource_config = ResourceConfig(
        kind="fake-person",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"fake-person"',
                )
            )
        ),
    )

    result = await processor.handle_event(event.payload, resource_config)

    assert len(result.deleted_raw_results) == 1
    assert result.deleted_raw_results[0]["id"] == "person-123"
    assert len(result.updated_raw_results) == 0


@pytest.mark.asyncio
async def test_webhook_processor_handle_event_create(
    monkeypatch: Any,
) -> None:
    """Test webhook processor handles create/update events correctly"""
    event = WebhookEvent(
        trace_id="test-trace",
        headers={},
        payload={"type": "create", "person_id": "person-123"},
    )

    # Mock get_random_person_from_batch to return a test person
    async def mock_get_random_person() -> Dict[Any, Any]:
        return FAKE_PERSON_RAW

    monkeypatch.setattr(
        "webhook_processors.get_random_person_from_batch",
        mock_get_random_person,
    )

    processor = FakePersonWebhookProcessor(event)
    resource_config = ResourceConfig(
        kind="fake-person",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"fake-person"',
                )
            )
        ),
    )

    result = await processor.handle_event(event.payload, resource_config)

    assert len(result.updated_raw_results) == 1
    assert result.updated_raw_results[0]["id"] == FAKE_PERSON_RAW["id"]
    assert len(result.deleted_raw_results) == 0


@pytest.mark.asyncio
async def test_custom_entity_processor(get_mocked_ocean_app: Any) -> None:
    """Test that FakeEntityProcessor is used and works correctly"""
    from integration import FakeEntityProcessor
    from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
        JQEntityProcessor,
    )

    app = get_mocked_ocean_app()

    # Verify the integration uses FakeEntityProcessor
    # Check that the entity processor is an instance of FakeEntityProcessor
    assert isinstance(app.integration.entity_processor, FakeEntityProcessor)

    # Verify FakeEntityProcessor extends JQEntityProcessor
    assert issubclass(FakeEntityProcessor, JQEntityProcessor)

    # Verify it has the _search method
    assert hasattr(FakeEntityProcessor, "_search")
