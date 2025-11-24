from typing import Any, AsyncGenerator, List, Dict

from port_ocean.helpers.async_client import OceanAsyncClient


class StreamingClientWrapper:
    def __init__(self, http_client: OceanAsyncClient):
        self._client = http_client

    async def stream_json(
        self,
        url: str,
        target_items_path: str,
        **kwargs: Any,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        A wrapper that provides a unified async generator interface for both streaming
        and non-streaming HTTP GET requests.

        :param url: The URL to request.
        :param target_items_path: A JMESPath string to extract the list of items
                                  from the JSON response (e.g., 'results'). The wrapper
                                  will automatically adapt this for the streaming parser.
        :param kwargs: Additional arguments for the HTTP request.
        """
        # ijson needs a path to the items inside the array, e.g., "results.item"
        streaming_path = f"{target_items_path}.item"
        stream_response = await self._client.get_stream(url, **kwargs)
        json_stream = stream_response.get_json_stream(target_items=streaming_path)
        async for items_batch in json_stream:
            yield items_batch
