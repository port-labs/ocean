# Jira

Integration to bring information from Jira into Port

## Development Requirements

- Python3.11.0
- Poetry (Python Package Manager)
- Port-Ocean

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
The Jira integration suggested folder structure is as follows:

```
Jira/
├─ main.py
├─ pyproject.toml
└─ Dockerfile
```