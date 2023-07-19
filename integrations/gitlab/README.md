# gitlab

Gitlab integration for Port using Port-Ocean Framework

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)

## Installation

```sh
make install
```

## Runnning Localhost
```sh
make run
```
or
```sh
ocean sail
```

## Running Tests

`make test`

## Access Swagger Documentation

> <http://localhost:8080/docs>

## Access Redoc Documentation

> <http://localhost:8080/redoc>


## Folder Structure
The gitlab integration suggested folder structure is as follows:

```
gitlab/
├─ gitlab_integration/      # The integration logic
│  ├─ core/                 # The core logic of the integration
│  ├─ events/               # All the event listeners to the different types of objects in gitlab
│  ├─ ocean.py              # All the ocean implementations with all the @ocean.on_resync implementations
│  ├─ custom_integration.py # Custom implementation of the port integration with git related logic
│  ├─ bootstrap.py          # The bootstrap file that will be used to start the integration and install all the webhooks
│  └─ ...
├─ main.py                  # The main exports the custom Ocean logic to the ocean sail command
└─ ...
```
