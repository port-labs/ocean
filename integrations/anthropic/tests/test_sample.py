"""Sample tests for Anthropic integration."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from client import AnthropicClient


@pytest.fixture
def anthropic_client():
    """Fixture to create a test Anthropic client."""
    return AnthropicClient(api_key="test-key")


@pytest.mark.asyncio
async def test_api_keys_generation(anthropic_client):
    """Test API keys data generation."""
    api_keys = []
    async for keys_batch in anthropic_client.get_api_keys():
        api_keys.extend(keys_batch)
    
    assert len(api_keys) > 0
    assert "id" in api_keys[0]
    assert "key_prefix" in api_keys[0]
    assert "status" in api_keys[0]


@pytest.mark.asyncio  
async def test_usage_data_structure(anthropic_client):
    """Test that usage data has expected structure."""
    # Mock the HTTP request to avoid actual API calls
    anthropic_client._make_request = AsyncMock(return_value={"data": [
        {
            "time_bucket": "2024-01-01T00:00:00Z",
            "input_tokens": 1000,
            "output_tokens": 500,
            "model": "claude-3-opus-20240229"
        }
    ]})
    
    usage_data = []
    async for data_batch in anthropic_client.get_usage_data():
        usage_data.extend(data_batch)
    
    assert len(usage_data) > 0
    assert "time_bucket" in usage_data[0]
    assert "input_tokens" in usage_data[0]


@pytest.mark.asyncio
async def test_cost_data_structure(anthropic_client):
    """Test that cost data has expected structure."""
    # Mock the HTTP request to avoid actual API calls
    anthropic_client._make_request = AsyncMock(return_value={"data": [
        {
            "date": "2024-01-01",
            "total_cost_usd": 12.50,
            "model": "claude-3-opus-20240229"
        }
    ]})
    
    cost_data = []
    async for data_batch in anthropic_client.get_cost_data():
        cost_data.extend(data_batch)
    
    assert len(cost_data) > 0
    assert "date" in cost_data[0]
    assert "total_cost_usd" in cost_data[0]


@pytest.mark.asyncio
async def test_connection_test_failure(anthropic_client):
    """Test connection test handles failures gracefully."""
    # Mock failed request
    anthropic_client._make_request = AsyncMock(side_effect=Exception("API Error"))
    
    result = await anthropic_client.test_connection()
    assert result is False