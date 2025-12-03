# harbor-server

An integration used to import harbor-server resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/) *Replace this link with a link to this integration's documentation*

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)


harbor/
├── __init__.py                    # Package initialization
├── main.py                        # Integration entry point
├── constants.py                   # Constants and enums (your existing file)
│
├── config/                        # Configuration models
│   ├── __init__.py
│   ├── app_config.py             # PortAppConfig and ResourceConfigs
│   └── selectors.py              # Selector classes
│
├── client/                        # API client layer
│   ├── __init__.py
│   └── harbor_client.py          # HarborClient implementation
│
├── core/                          # Core integration logic
│   ├── __init__.py
│   ├── resync.py                 # Resync handlers (@ocean.on_resync)
│   └── startup.py                # Startup logic (@ocean.on_start)
│
├── webhooks/                      # Webhook handling
│   ├── __init__.py
│   ├── manager.py                # HarborWebhookManager
│   ├── processors/               # Event processors
│   │   ├── __init__.py
│   │   ├── artifact_processor.py
│   │   ├── project_processor.py
│   │   └── repository_processor.py
│   └── validators.py             # Signature verification
│
└── utils/                         # Utility functions
    ├── __init__.py
    └── helpers.py                # Shared helper functions
