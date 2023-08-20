The following event listener types are supported:

- [`POLLING`](./event-listener.md#polling) - the integration will automatically query Port for updates in the integration configuration and perform a resync if changes are detected
- [`KAFKA`](./event-listener.md#kafka) - the integration will consume incoming resync requests from your dedicated Kafka topic, provisioned to you by Port
- [`WEBHOOK`](./event-listener.md#webhook) - the integration will be triggered by HTTP POST requests made to the URL provided in the configuration
