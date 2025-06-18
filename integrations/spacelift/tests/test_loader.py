import pytest
from spacelift.loader import SpaceliftLoader

@pytest.mark.asyncio
async def test_run_loader(mocker):
    mock_context = mocker.Mock()
    mock_context.resources.write_resource = mocker.AsyncMock()

    loader = SpaceliftLoader(mock_context)
    loader.client.query = mocker.AsyncMock(return_value={
        "stacks": [
            {"id": "stack1", "name": "Infra Stack", "description": "desc"}
        ]
    })
    await loader.run()
    mock_context.resources.write_resource.assert_called_once()