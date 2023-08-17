The following event listener types are supported:

- [`KAFKA`](./event-listener.md#kafka) - in this event listener type, the integration will consume incoming resync requests from your dedicated Kafka topic, provisioned to you by Port
- [`WEBHOOK`](./event-listener.md#webhook) - in this event listener type, the integration will be triggered by HTTP POST requests made to the URL provided in the configuration
- [`POLLING`](./event-listener.md#polling) - in this event listener type, the integration will automatically query Port for updates in the integration configuration and perform a resync if changes are detected
