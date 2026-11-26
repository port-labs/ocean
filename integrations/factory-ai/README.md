# Factory.ai

An integration used to import [Factory.ai](https://factory.com) (Droid / Software Factory) resources into Port.

#### Install & use the integration - [Factory Public API documentation](https://docs.factory.com/api-reference)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.port.io/developing-an-integration/)

## Configuration

| Spec field | Env var | Required | Default |
|---|---|---|---|
| `factoryApiKey` | `OCEAN__INTEGRATION__CONFIG__FACTORY_API_KEY` | yes | — |
| `factoryApiHost` | `OCEAN__INTEGRATION__CONFIG__FACTORY_API_HOST` | no | `https://api.factory.ai` |

Create an API key at [Factory API keys](https://app.factory.ai/settings/api-keys).

Factory has no outbound webhooks, so this integration does not process live events.
