Use `httpx` package instead if `requests` for making HTTP requests and take advantage of its async & connection re-use
capabilities.

```python showLineNumbers
import httpx

client = httpx.AsyncClient()
response = await client.get('https://example.com')
```

:::tip
Reuse the async client across your integration to take advantage of connection re-use.
:::

:::warning
Usage of `requests` package will cause the web requests to be made synchronously and will block the event loop.
:::

:::danger
The integration can be used with a [Kafka event listener](../framework/features/event-listener.md#kafka), which runs
in a separate thread. Make sure to use your client in a thread-safe manner. The async client will throw an exception if is used in a different event loop than the one it was created in.
:::
