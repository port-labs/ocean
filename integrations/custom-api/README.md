# Custom API Integration

This Ocean integration ingests data from a generic API route into Port, based on mapping rules defined in `port-app-config.yaml`.

## 🔁 How it works

- Fetches data from a configured API endpoint (`api_url`)
- Transforms and maps the data using `port-app-config.yaml`
- Sends `operation: create/update` or `delete` webhook requests to Port
- Populates entities of the blueprint: `apiItem`

## ⚙️ Setup

1. Update `.port/spec.yaml` with the correct `type`, description, and configuration keys
2. Define entity mappings in `.port/port-app-config.yaml`
3. Run locally with environment variables:

```bash
export OCEAN__PORT__CLIENT_ID=your-client-id
export OCEAN__PORT__CLIENT_SECRET=your-client-secret
export OCEAN__INTEGRATION__CONFIG__API_URL=https://your.api/data

# Optional if your API needs a token
export OCEAN__INTEGRATION__CONFIG__AUTH_TOKEN=your-token

ocean sail -O
