# {{cookiecutter.integration_name}}

{{cookiecutter.integration_short_description}}

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
The {{cookiecutter.integration_name}} integration suggested folder structure is as follows:

```
{{cookiecutter.integration_name}}/
├─ main.py
├─ pyproject.toml
└─ Dockerfile
```